# Midterm Project Approach

## Problem Scale

The implementation is designed for the requested upper bounds:

| Parameter | Upper bound |
| --- | ---: |
| Stations | 100 |
| Cars | 1,000 |
| Car levels | 10 |
| Orders | 10,000 |
| Planning horizon | 100 days |
| Moving time budget | 1,000,000 minutes |

All algorithms use the same feasibility rules: a car can serve an order at its own level or one level lower, it must arrive at the pick-up station 30 minutes before pick-up, and after returning from an order it needs 4 hours before it can serve the next order.

## IP Solver

`ip_solver.py` builds an arc-flow integer program over feasible car-order and order-order transitions.

Variables:

- `y_k = 1` if order `k` is accepted.
- `start_{c,k} = 1` if car `c` serves order `k` as its first order.
- `link_{c,i,j} = 1` if car `c` serves order `j` immediately after order `i`.

The business objective is:

```text
maximize accepted_revenue - 2 * rejected_revenue
```

Since total revenue is constant, this is equivalent to maximizing accepted revenue inside the IP. The solver reports both accepted revenue and the final profit with rejection compensation.

Constraint families:

- each accepted order has exactly one predecessor;
- each car starts at most one route;
- per-car flow continuity is enforced at every order;
- total relocation time is at most `B`.

The model is useful for the five public instances and small generated cases, but it is not intended for the maximum data range because the number of feasible order-order arc variables can grow very large.

## Algo1: Greedy Insertion

`algorithm_module.py` is the primary fast baseline.

For small cases (`orders <= 80` and `cars <= 120`) it first tries the IP solver with a short 20-second limit unless `raw_test=True`.

For large cases it uses greedy insertion:

1. Sort orders by descending revenue, then earlier pick-up time, then order ID.
2. For each order, scan all compatible cars.
3. For each car, insert the order into the route position determined by pick-up time.
4. Check only the predecessor and successor around that insertion.
5. Choose the feasible insertion with the smallest extra moving time.
6. Break ties by smaller upgrade, smaller idle time, and smaller car ID.

This algorithm is conservative and very fast. It is especially strong on dense generated cases because it can accept many orders while preserving the moving budget.

Complexity:

```text
O(K log K + K C log K)
```

where `K` is the number of orders and `C` is the number of cars.

## Algo2: Order-Node DP Trajectories

`heuristic_algo2.py` repeatedly builds maximum-score trajectories for cars over currently unassigned orders.

For each lambda value, car parity order, and car ordering mode, it:

1. keeps a set of unassigned orders;
2. processes cars in the selected order;
3. solves a single-car order-node DP;
4. assigns the selected trajectory to that car;
5. removes those orders from later cars.

The DP sorts candidate orders by pick-up time. For an order `j`, it scans a bounded number of previous order nodes and checks whether the car can move from the previous return station to `j` in time. The transition score is:

```text
3 * R_j / sum_R - lambda * moving_time / (1 + B)
```

For large cases, candidate orders are truncated by revenue and the predecessor scan is reduced to keep runtime controlled. Algo2 is slower than Algo1, but it is useful on public instances where a carefully chosen route structure beats simple greedy insertion.

Approximate complexity per car:

```text
O(M * P)
```

where `M` is the number of candidate orders for that car and `P` is the predecessor scan cap (`260` on small/medium cases, `35` on large cases).

## Algo3: Batch Ratio Repair

`heuristic_algo3.py` starts from Algo1 and performs local repair.

Each repair iteration:

1. computes each current car trajectory's efficiency:

```text
route_reward / (1 + route_moving_time)
```

2. samples up to 5 low-efficiency trajectories using inverse softmax;
3. releases all orders on those trajectories;
4. shuffles the selected cars;
5. rebuilds each selected car with a top-10 station DP;
6. rolls back the whole repair if total profit becomes worse.

The single-car repair DP uses:

```text
sum_reward / (1 + sum_moving_time)
```

This avoids a lambda loop and makes many random repair attempts possible within the time limit. Algo3 is most helpful when Algo1 leaves enough rejected orders for local route exchanges to matter.

Approximate repair complexity:

```text
O(iterations * batch_size * K * top_k)
```

with `batch_size = 5` and `top_k = 10`.

## Benchmark Summary

The final comparison used a 140-second per-testcase time limit for Algo2 and Algo3.

| Instance | Algo1 | Algo2 | Algo3 | Best |
| --- | ---: | ---: | ---: | --- |
| instance01 | **27,900** | **27,900** | **27,900** | tie |
| instance02 | 35,100 | **49,500** | 35,100 | Algo2 |
| instance03 | **50,000** | **50,000** | **50,000** | tie |
| instance04 | 36,500 | **79,400** | 45,200 | Algo2 |
| instance05 | **106,800** | **106,800** | **106,800** | tie |
| imbalanced_flow_01 | **22,192,000** | 21,209,200 | **22,192,000** | Algo1/Algo3 |
| large_dense_01 | **4,946,628,700** | 4,858,208,200 | **4,946,628,700** | Algo1/Algo3 |
| low_level_heavy_01 | 2,639,700 | 2,613,900 | **2,646,000** | Algo3 |
| small_balanced_01 | 649,900 | 681,700 | **690,400** | Algo3 |

Takeaway: Algo1 is the strongest fast baseline. Algo2 is best on public instances where route structure matters. Algo3 is a useful local-improvement wrapper for generated small and low-level-heavy cases.

## Test Case Generation

`experiments/generate_testcases.py` creates instances in the same five-section TXT format as the public data. It supports four scenarios:

| Scenario | Purpose |
| --- | --- |
| `small_balanced` | Small balanced cases. |
| `low_level_heavy` | Many low-level requests, testing upgrade use. |
| `imbalanced_flow` | Pick-ups and returns concentrated in different station groups. |
| `large_dense` | Maximum-scale stress case. |

Run:

```bash
~/myenv/bin/python experiments/generate_testcases.py --per-scenario 5
```

Generated files are written to `experiments/generated_data/`.
