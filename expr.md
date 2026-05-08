# Heuristic Experiments

## Goal

We tested whether `heuristic_algo2` can be improved by replacing the order-predecessor DP with a sweep-line station DP:

```text
candidate_pool[ready_time] -> val[station]
```

For each order, all candidates that are ready by `pickup_time - 30` are released. The DP then scans all stations and picks the best feasible predecessor:

```text
val[s] + 3R_j / sumR - lambda * T[s, pickup_j] / (1 + B)
```

After accepting order `j`, the resulting candidate is pushed back into the future pool at `return_j + 240`.

This removes the old `max_prev_scan` truncation. The single-car route DP is now roughly:

```text
O(#candidate_orders * #stations)
```

## Strategies Tried

The first sweep version let each car take an unrestricted best path. It was fast, but on dense large cases early cars consumed too many orders and relocation budget.

We then added route control strategies:

| Strategy | Budget quota | Route length cap |
| --- | ---: | ---: |
| `unlimited` | none | none |
| `quota_1.0_len_1.0` | `1.0 * remaining_budget / cars_left` | `1.0 * orders_left / cars_left` |
| `quota_1.5_len_1.5` | `1.5 * remaining_budget / cars_left` | `1.5 * orders_left / cars_left` |
| `quota_2.0_len_1.5` | `2.0 * remaining_budget / cars_left` | `1.5 * orders_left / cars_left` |
| `quota_1.5_len_2.0` | `1.5 * remaining_budget / cars_left` | `2.0 * orders_left / cars_left` |

`heuristic_algo2` tries these strategies within the time guard and keeps the best feasible profit.

## Public Instances

Raw `heuristic_algo2` results after the sweep/quota change:

| Instance | Profit | Optimal | Gap | Accepted | Moving |
| --- | ---: | ---: | ---: | ---: | ---: |
| instance01 | 27,900 | 27,900 | 0 | 5/5 | 180/180 |
| instance02 | 49,500 | 49,500 | 0 | 9/10 | 1410/1800 |
| instance03 | 50,000 | 50,000 | 0 | 9/10 | 0/0 |
| instance04 | 82,400 | 82,400 | 0 | 17/20 | 5190/5500 |
| instance05 | 106,800 | 106,800 | 0 | 8/10 | 1140/1200 |

This improves over the previous raw `heuristic_algo2` on instance04, where the old version had a 3,000 gap.

## Generated Smoke Instances

Raw comparison:

| Instance | Algo1 Profit | Algo2 Raw Profit | Better Raw |
| --- | ---: | ---: | --- |
| `small_balanced_01` | 649,900 | 716,200 | Algo2 |
| `low_level_heavy_01` | 2,639,700 | 2,409,900 | Algo1 |
| `imbalanced_flow_01` | 22,192,000 | 19,786,600 | Algo1 |
| `large_dense_01` | 4,946,628,700 | -6,631,607,300 | Algo1 |

Default `heuristic_algo2(raw_test=False)` first uses Algo1 as a baseline and only keeps Algo2 if it improves the objective. Therefore:

| Instance | Default Profit | Source |
| --- | ---: | --- |
| `small_balanced_01` | 716,200 | Algo2 |
| `low_level_heavy_01` | 2,639,700 | Algo1 baseline |
| `imbalanced_flow_01` | 22,192,000 | Algo1 baseline |
| `large_dense_01` | 4,946,628,700 | Algo1 baseline |

## Takeaway

The sweep DP is a better single-car route solver than the predecessor-truncated DP, and it fixed public instance04. However, on dense large instances, raw Algo2 still over-commits early cars and hurts global coverage. Keeping Algo1 as the default baseline is important.

Current recommendation:

```text
Submit heuristic_algorithm / heuristic_algorithm2 with raw_test=False behavior.
Use raw_test=True only for experiments.
```

## Ratio-Only Greedy Trajectory Test

We also tested a simpler version requested during optimization:

```text
score(path) = accepted_sales(path) / (1 + moving_time(path))
```

This version drops lambda search, route caps, and strategy search. Each car greedily takes one sweep-DP trajectory, then masks the selected orders. The intended complexity is:

```text
O(#cars * #orders_per_car * #stations)
```

Runtime was acceptable: the four generated smoke instances finished in about 67 seconds total on the local machine. However, the score quality was poor because the ratio objective over-penalizes relocation minutes and strongly prefers short or zero-relocation routes.

Public raw results:

| Instance | Profit | Optimal | Gap |
| --- | ---: | ---: | ---: |
| instance01 | 7,800 | 27,900 | 20,100 |
| instance02 | -14,700 | 49,500 | 64,200 |
| instance03 | 50,000 | 50,000 | 0 |
| instance04 | -7,300 | 82,400 | 89,700 |
| instance05 | -46,800 | 106,800 | 153,600 |

Generated smoke raw results:

| Instance | Algo2 Ratio Raw Profit | Default Profit |
| --- | ---: | ---: |
| `small_balanced_01` | 384,100 | 649,900 |
| `low_level_heavy_01` | 1,927,800 | 2,639,700 |
| `imbalanced_flow_01` | 11,850,100 | 22,192,000 |
| `large_dense_01` | 314,791,000 | 4,946,628,700 |

Conclusion: the ratio-only version is fast, but it should not be kept as the final raw Algo2. The previous sweep+quota version is better for public cases, while default baseline protection remains necessary for large dense cases.

### Car Ordering Test

We then tried two car orders for the ratio-only greedy version:

```text
1. cars sorted by level decreasing
2. cars sorted by hourly rate F decreasing
```

Because hourly rates are monotone with levels in the current generators/public data, these two orders are nearly identical. Public raw results stayed poor:

| Instance | Profit | Gap |
| --- | ---: | ---: |
| instance01 | 7,800 | 20,100 |
| instance02 | -14,700 | 64,200 |
| instance03 | 50,000 | 0 |
| instance04 | -7,600 | 90,000 |
| instance05 | -46,800 | 153,600 |

Generated raw results with the two-order choice:

| Instance | Profit | Accepted | Moving |
| --- | ---: | ---: | ---: |
| `small_balanced_01` | 165,400 | 86 | 3,660/8,000 |
| `low_level_heavy_01` | 2,246,100 | 256 | 6,450/25,000 |
| `imbalanced_flow_01` | 7,517,800 | 624 | 43,650/80,000 |
| `large_dense_01` | -50,967,800 | 6,622 | 181,380/1,000,000 |

This confirms that car ordering alone does not fix the ratio objective. The limiting factor is the path score itself: `sales / (1 + moving_time)` avoids relocation too strongly and leaves too many profitable orders unserved.

### Level Virtual Source Test

We then changed the ratio-only greedy implementation from enumerating cars to enumerating levels. For a level `l`, all unused level-`l` cars are inserted as virtual source candidates. The sweep DP chooses the best trajectory among that level's remaining cars, returns the selected car ID, removes the selected orders, and appends level `l` back to the queue if cars of that level remain:

```text
candidate_levels = [L, L-1, ..., 1]
for l in candidate_levels:
    solve_level(l)
    if unused level-l cars remain:
        candidate_levels.append(l)
```

Public raw results remained poor under the ratio objective:

| Instance | Profit | Gap |
| --- | ---: | ---: |
| instance01 | 7,800 | 20,100 |
| instance02 | -14,700 | 64,200 |
| instance03 | 50,000 | 0 |
| instance04 | -8,500 | 90,900 |
| instance05 | -46,800 | 153,600 |

Generated raw results:

| Instance | Profit | Accepted | Moving |
| --- | ---: | ---: | ---: |
| `small_balanced_01` | 375,400 | 88 | 3,270/8,000 |
| `low_level_heavy_01` | 2,221,500 | 248 | 4,920/25,000 |
| `imbalanced_flow_01` | 13,396,000 | 655 | 44,460/80,000 |
| `large_dense_01` | 1,032,364,300 | 6,681 | 173,640/1,000,000 |

Level virtual sources improve the dense large raw result compared with the car-enumeration ratio test, but the result is still far below Algo1. The conclusion is unchanged: the batching idea is useful, but the ratio-only score is not a good final objective.

## Previous Version Comparison

After committing the current level-batched experiment, we exported the previous committed `heuristic_algo2.py` from `HEAD~1` and ran the same raw tests. That previous version is the order-node DP with `max_prev_scan`, normalized lambda weights, and greedy masking.

Previous version public raw results:

| Instance | Profit | Optimal | Gap | Accepted | Moving |
| --- | ---: | ---: | ---: | ---: | ---: |
| instance01 | 27,900 | 27,900 | 0 | 5/5 | 180/180 |
| instance02 | 49,500 | 49,500 | 0 | 9/10 | 1410/1800 |
| instance03 | 50,000 | 50,000 | 0 | 9/10 | 0/0 |
| instance04 | 79,400 | 82,400 | 3,000 | 16/20 | 5100/5500 |
| instance05 | 106,800 | 106,800 | 0 | 8/10 | 1110/1200 |

Previous version generated smoke raw results:

| Instance | Profit | Accepted | Moving |
| --- | ---: | ---: | ---: |
| `small_balanced_01` | 681,700 | 90/120 | 7980/8000 |
| `low_level_heavy_01` | 2,613,900 | 280/300 | 24870/25000 |
| `imbalanced_flow_01` | 21,209,200 | 691/800 | 79980/80000 |
| `large_dense_01` | 4,858,208,200 | 7070/10000 | 934890/1000000 |

Comparison against the current level-batched top-k station version:

| Instance | Previous Raw | Current Raw | Better |
| --- | ---: | ---: | --- |
| `small_balanced_01` | 681,700 | 679,600 | Previous |
| `low_level_heavy_01` | 2,613,900 | 2,602,200 | Previous |
| `imbalanced_flow_01` | 21,209,200 | 15,303,700 | Previous |
| `large_dense_01` | 4,858,208,200 | 1,231,934,200 | Previous |

Conclusion: the level-batched virtual-source idea is elegant, and top-k station transfer is fast, but the current approximation loses too much quality on generated large instances. The previous order-node DP with `max_prev_scan` is still the better raw Algo2 candidate.

## Order-Node DP Lambda Sweep

After restoring the order-node DP version, we ran a fixed lambda sweep with a 30-minute cap per lambda:

```text
[0, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0]
```

The benchmark was run with `raw_test=True`, so these numbers are pure Algo2 without the Algo1/IP wrapper. Full per-lambda results, including runtime for every lambda, are saved in `benchmark_results/lambda_benchmark.md` and `benchmark_results/lambda_benchmark.csv`.

Total benchmark wall time: 463.71 seconds.

Best result by instance:

| Instance | Best Lambda | Profit | Accepted | Moving |
| --- | ---: | ---: | ---: | ---: |
| `instance01` | 0 | 27,900 | 5/5 | 180/180 |
| `instance02` | 0 | 49,500 | 9/10 | 1410/1800 |
| `instance03` | 0 | 50,000 | 9/10 | 0/0 |
| `instance04` | 0.15 | 79,400 | 16/20 | 4680/5500 |
| `instance05` | 0.3 | 102,300 | 7/10 | 1170/1200 |
| `small_balanced_01` | 0.5 | 660,400 | 90/120 | 7590/8000 |
| `low_level_heavy_01` | 0.5 | 2,613,600 | 278/300 | 24990/25000 |
| `imbalanced_flow_01` | 0.75 | 21,095,800 | 679/800 | 71430/80000 |
| `large_dense_01` | 0.3 | 4,875,695,800 | 7330/10000 | 999180/1000000 |

Takeaways:

- Public instances mostly prefer small lambda values, with the exception of instance04/05.
- Generated smoke instances prefer stronger relocation penalty: `0.3`, `0.5`, or `0.75`.
- Large dense quality recovers to the previous order-node DP range: best profit is 4.875B at lambda `0.3`.
- The 30-minute cap is not binding on these tests. The largest per-lambda runtime was about 28.25 seconds on `large_dense_01`.

## Algo2 Ternary Search

The fixed lambda sweep suggested that the response curve is often close to unimodal on generated instances, so we added `algo2_trisearch.py`. It searches lambda in `[0, 1]` for 20 ternary-search iterations. Each iteration evaluates two lambda values with `heuristic_algorithm2(..., lambdas=[lambda], raw_test=True)`.

Full iteration logs are saved in `benchmark_results/algo2_trisearch.md` and `benchmark_results/algo2_trisearch.csv`.

Total benchmark wall time: 1,557.61 seconds.

Best result by instance:

| Instance | Best Lambda | Profit | Accepted | Moving | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: |
| `instance01` | 0.33333333 | 27,900 | 5/5 | 180/180 | 0.16s |
| `instance02` | 0.33333333 | 49,500 | 9/10 | 1410/1800 | 0.53s |
| `instance03` | 0.33333333 | 50,000 | 9/10 | 0/0 | 0.05s |
| `instance04` | 0.33333333 | 79,400 | 16/20 | 4680/5500 | 1.02s |
| `instance05` | 0.44444444 | 102,300 | 7/10 | 1050/1200 | 0.40s |
| `small_balanced_01` | 0.35390947 | 720,400 | 93/120 | 7980/8000 | 13.29s |
| `low_level_heavy_01` | 0.42844079 | 2,636,400 | 284/300 | 24690/25000 | 107.11s |
| `imbalanced_flow_01` | 0.63511660 | 21,398,500 | 702/800 | 79830/80000 | 481.45s |
| `large_dense_01` | 0.29429796 | 4,875,626,200 | 7340/10000 | 999390/1000000 | 953.60s |

Comparison with the fixed lambda grid:

| Instance | Fixed Grid Best | Ternary Best | Delta |
| --- | ---: | ---: | ---: |
| `instance01` | 27,900 | 27,900 | 0 |
| `instance02` | 49,500 | 49,500 | 0 |
| `instance03` | 50,000 | 50,000 | 0 |
| `instance04` | 79,400 | 79,400 | 0 |
| `instance05` | 102,300 | 102,300 | 0 |
| `small_balanced_01` | 660,400 | 720,400 | +60,000 |
| `low_level_heavy_01` | 2,613,600 | 2,636,400 | +22,800 |
| `imbalanced_flow_01` | 21,095,800 | 21,398,500 | +302,700 |
| `large_dense_01` | 4,875,695,800 | 4,875,626,200 | -69,600 |

Takeaway: ternary search is promising for generated instances. It improves three generated smoke cases and essentially ties `large_dense_01`, but it costs about 40 lambda evaluations per instance. For the final solver, a hybrid strategy is attractive: keep a small fixed grid for public/small stability, then run ternary search around the best grid region when enough time remains.

## Algo1 vs Algo2 Ternary Search

We also compared Algo1 raw insertion against the best result from Algo2 ternary search. Full results are saved in `benchmark_results/algo1_vs_trisearch.md` and `benchmark_results/algo1_vs_trisearch.csv`.

| Instance | Algo1 Profit | Trisearch Profit | Delta |
| --- | ---: | ---: | ---: |
| `instance01` | 27,900 | 27,900 | 0 |
| `instance02` | 35,100 | 49,500 | +14,400 |
| `instance03` | 50,000 | 50,000 | 0 |
| `instance04` | 36,500 | 79,400 | +42,900 |
| `instance05` | 106,800 | 102,300 | -4,500 |
| `small_balanced_01` | 649,900 | 720,400 | +70,500 |
| `low_level_heavy_01` | 2,639,700 | 2,636,400 | -3,300 |
| `imbalanced_flow_01` | 22,192,000 | 21,398,500 | -793,500 |
| `large_dense_01` | 4,946,628,700 | 4,875,626,200 | -71,002,500 |

Takeaway: Algo2 ternary search is useful as an improvement attempt, especially on public02/public04 and `small_balanced_01`, but Algo1 remains the stronger baseline for dense generated instances and is much faster. The final wrapper should keep Algo1's solution and only overwrite it when Algo2 finds a higher-profit solution.
