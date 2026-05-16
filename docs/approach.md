# Algorithm Approach

The final method is a three-stage heuristic designed for the project scale:
up to 100 stations, 1,000 cars, 10 service levels, 10,000 orders, and a
3-minute time limit.

All stages use the same feasibility rules:

- a car can serve an order at the same level or one level lower;
- the car must be ready at the pick-up station 30 minutes before pick-up;
- after an order returns, the car needs 4 hours before serving another order;
- total relocation time must not exceed the moving budget.

The objective is:

```text
profit = accepted_revenue - 2 * rejected_revenue
```

Since total revenue is fixed for one instance, improving profit is equivalent to
increasing accepted revenue while respecting feasibility and relocation budget.

## Heuristic 1: Greedy Insertion Baseline

The first heuristic is a fast greedy insertion method. Orders are sorted by
descending revenue, then earlier pick-up time, then order ID. For each order, the
algorithm scans compatible cars and tries to insert the order into the car route
at the chronological position implied by pick-up time.

For each candidate insertion, it only needs to check the local predecessor and
successor around the inserted order. The chosen insertion minimizes additional
moving time, with tie-breakers for smaller upgrade use, smaller idle time, and
smaller car ID.

This baseline is intentionally conservative. It is very fast, accepts many
orders on dense and easy instances, and produces a stable feasible plan for the
later improvement stage.

## Heuristic 2: Demand-Aware Pre-Build

The second heuristic builds a stronger initial solution by combining several
demand-aware greedy variants. It estimates future demand value by station,
service level, and time bucket. A car assignment is scored by:

- direct value from accepting the order;
- future value of ending at the order's return station;
- opportunity cost of moving away from the current station;
- relocation time penalty;
- idle-time penalty;
- upgrade penalty.

For large instances, only a small set of robust variants is used. This keeps the
pre-build phase bounded while still capturing important spatial and temporal
patterns such as hub returns, peak demand, and tight relocation budgets.

In the submission-oriented module, this pre-build phase caps the internal
Algo5-style heuristic at 30 seconds. This prevents the initial solution builder
from consuming the full global time limit.

## Final Optimization: Local IP Repair

After the pre-build solution is ready, the final stage spends the remaining time
on local optimization. It repeatedly selects a small batch of low-efficiency car
routes, releases their orders, and solves a restricted arc-flow IP over:

- the selected cars;
- their released orders;
- a capped set of high-value currently unassigned orders.

The local IP uses the same structure as the full model:

- `y_k` indicates whether order `k` is accepted;
- `start_{c,k}` indicates whether car `c` starts with order `k`;
- `link_{c,i,j}` indicates whether car `c` serves order `j` immediately after
  order `i`.

The repaired routes are accepted only if they improve total profit and remain
within the relocation budget. Each local IP solve is capped by the remaining
wall-clock time and a small per-repair limit, so the algorithm can return a
valid solution even when the Gurobi improvement phase is unavailable or runs out
of time.

## Time Budget

The final entry point is `heuristic_algorithm(instance_file, max_seconds=170)`.
It uses one global deadline:

```text
pre_build:
  greedy baseline
  demand-aware pre-build, capped at 30 seconds

local_ip_improve:
  uses the remaining global time
```

This layout leaves margin under the 180-second grading limit while still using
extra time productively on hard instances.
