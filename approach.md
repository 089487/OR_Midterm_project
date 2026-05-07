# Midterm Project Approach

## IP Solver

I model each car schedule as a path in a directed acyclic graph.

- A node is an order.
- A source node is an initial car.
- A car-to-order arc exists if the car level can serve the order and the car can be moved from its initial station to the pick-up station by 30 minutes before pick-up.
- An order-to-order arc exists for a specific car if that car can serve both order levels, and the first order's return station can be cleaned and moved to the next pick-up station by 30 minutes before the next pick-up.
- The moving time on each selected arc consumes the global budget `B`.

Decision variables:

- `y_k = 1` if order `k` is accepted.
- `start_{c,k} = 1` if car `c` serves order `k` as its first order.
- `link_{c,i,j} = 1` if car `c` serves order `j` immediately after order `i`.

The business objective is

```text
maximize sum accepted R_k - sum rejected 2R_k
```

Equivalently, because `-2 * sum R_k` is constant, the selected orders are the same as when maximizing accepted sales revenue:

```text
maximize sum accepted R_k
```

The solver reports both accepted sales revenue and the profit value with rejection compensation. The constraints enforce one predecessor per accepted order, flow conservation for every car, at most one first order per car, and total relocation time no more than `B`.

The implementation is in `ip_solver.py`. It uses Gurobi and writes business-readable optimal plans to `plans/`.

One edge case is handled explicitly: if an order is picked up exactly at the start of the horizon and a car is already ready at that station, the order can be served immediately, as stated in the problem.

## Heuristic Algorithm

The heuristic in `algorithm_module.py` is a hybrid method.

For small instances (`K <= 80` and `C <= 120`), it calls the IP model with a short 20-second time limit. This gives optimal-quality answers for the five reference instances and for small benchmark cases.

For larger instances, it uses a fast greedy insertion rule:

1. Sort orders by higher revenue, then earlier pick-up time, then order ID.
2. For each order, scan all compatible cars, including one-level upgrades.
3. For each car, insert the order into the only possible time-sorted position in that car's current route.
4. Keep the insertion only if the previous order, the inserted order, and the next order remain feasible and the relocation budget is not exceeded.
5. Choose the feasible insertion with the smallest additional relocation time.
6. Break ties by preferring no upgrade, then smaller local idle time, then smaller car ID.

This rule is intentionally conservative. It protects high-revenue orders first, preserves relocation budget, avoids unnecessary upgrades, and keeps each car's schedule temporally tight.

## Time Complexity

Let:

- `K` be the number of orders.
- `C` be the number of cars.
- `S` be the number of stations.

For the large-instance branch, the heuristic sorts orders in `O(K log K)`. For each order it scans all cars. Each car route is maintained in pick-up-time order; finding the insertion point is logarithmic in that car's route length, and only the previous and next orders need feasibility checks. The total running time is:

```text
O(K log K + K C log K)
```

The memory usage is:

```text
O(K + C + S^2)
```

For the requested upper range, `K <= 10,000`, `C <= 1,000`, and `S <= 100`, this means at most about ten million car-order checks, which is suitable for a three-minute grading limit in Python.

## Test Case Generation

`generate_testcases.py` creates random instances in the same five-section TXT format as the reference data. It includes four scenarios:

| Scenario | Purpose |
| --- | --- |
| `small_balanced` | Small benchmark cases where the IP solver can often still solve optimally. |
| `low_level_heavy` | Many low-level requests, testing whether upgrades are used carefully. |
| `imbalanced_flow` | Pick-ups concentrated in one station group and returns in another, stressing relocation. |
| `large_dense` | Maximum-scale stress case matching the requested data range. |

The generator respects the requested upper bounds:

- stations up to 100
- cars up to 1,000
- car levels up to 10
- orders up to 10,000
- planning horizon up to 100 days
- moving budget up to 1,000,000 minutes

Run:

```bash
~/myenv/bin/python generate_testcases.py --per-scenario 5
```

This writes generated instances to `generated_data/`.

## Alternative Heuristic: Algo2

`heuristic_algo2.py` implements a second heuristic based on repeated maximum-weight car routes.

For a fixed lambda, each car solves a station-sweep routing subproblem over currently unassigned compatible orders. The normalized arc reward of appending order `j` after the previous state is:

```text
3R_j / sum_i R_i - lambda * relocation_time / (1 + B)
```

Candidate labels are released by a sweep line: after a car accepts an order, the resulting label is pushed into a pool keyed by `return time + 1 hour delay + 3 hours cleaning`, and only becomes available for later transitions after that ready time. Each station keeps the best currently available label. After one car chooses a route, all orders on that route are removed from the active linked lists and cannot be used by later cars.

To reflect the one-level upgrade rule, cars are processed by level from high to low:

- a level-l car only scans active orders of requested levels l and l-1
- among cars of the same level, the car with the best route DP value is selected next

For large instances, it automatically switches to a lighter mode by using fewer car-order modes and a smaller candidate pool per car. This keeps the idea usable without turning the route subproblem into a full-scale IP.

The implementation also has a wall-clock guard. By default it stops after about 165 seconds and returns the best complete plan found so far, leaving a buffer under the three-minute grading limit.
