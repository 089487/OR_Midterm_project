# Algo1 / Algo2 / Algo3 Comparison

Per-testcase time limit for timed heuristics: `140s`.

Total benchmark wall time: `761.31s`.

## Algorithm Summary

- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; each order is inserted into the feasible car route with the smallest extra relocation cost.
- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, then masks selected orders.
- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by `sumR / (1 + sum_move)`; worse full solutions are rolled back.

## Results

| Instance | Method | Profit | Accepted | Moving | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| `data/instance01.txt` | algo1 | 27900 | 5/5 | 180/180 | 0.01 |
| `data/instance01.txt` | algo2 | 27900 | 5/5 | 180/180 | 0.03 |
| `data/instance01.txt` | algo3 | 27900 | 5/5 | 180/180 | 3.70 |
| `data/instance02.txt` | algo1 | 35100 | 8/10 | 930/1800 | 0.00 |
| `data/instance02.txt` | algo2 | 49500 | 9/10 | 1410/1800 | 0.13 |
| `data/instance02.txt` | algo3 | 35100 | 8/10 | 930/1800 | 8.30 |
| `data/instance03.txt` | algo1 | 50000 | 9/10 | 0/0 | 0.00 |
| `data/instance03.txt` | algo2 | 50000 | 9/10 | 0/0 | 0.01 |
| `data/instance03.txt` | algo3 | 50000 | 9/10 | 0/0 | 1.54 |
| `data/instance04.txt` | algo1 | 36500 | 14/20 | 4110/5500 | 0.00 |
| `data/instance04.txt` | algo2 | 79400 | 16/20 | 5100/5500 | 0.24 |
| `data/instance04.txt` | algo3 | 45200 | 15/20 | 3810/5500 | 12.48 |
| `data/instance05.txt` | algo1 | 106800 | 8/10 | 1140/1200 | 0.00 |
| `data/instance05.txt` | algo2 | 106800 | 8/10 | 1110/1200 | 0.09 |
| `data/instance05.txt` | algo3 | 106800 | 8/10 | 1140/1200 | 7.86 |
| `generated_data_smoke/imbalanced_flow_01.txt` | algo1 | 22192000 | 799/800 | 75060/80000 | 0.16 |
| `generated_data_smoke/imbalanced_flow_01.txt` | algo2 | 21209200 | 691/800 | 79980/80000 | 140.06 |
| `generated_data_smoke/imbalanced_flow_01.txt` | algo3 | 22192000 | 799/800 | 75060/80000 | 93.62 |
| `generated_data_smoke/large_dense_01.txt` | algo1 | 4946628700 | 10000/10000 | 931080/1000000 | 4.66 |
| `generated_data_smoke/large_dense_01.txt` | algo2 | 4858208200 | 7070/10000 | 934890/1000000 | 140.15 |
| `generated_data_smoke/large_dense_01.txt` | algo3 | 4946628700 | 10000/10000 | 931080/1000000 | 141.42 |
| `generated_data_smoke/low_level_heavy_01.txt` | algo1 | 2639700 | 281/300 | 24990/25000 | 0.04 |
| `generated_data_smoke/low_level_heavy_01.txt` | algo2 | 2613900 | 280/300 | 24870/25000 | 46.39 |
| `generated_data_smoke/low_level_heavy_01.txt` | algo3 | 2646000 | 283/300 | 24930/25000 | 73.50 |
| `generated_data_smoke/small_balanced_01.txt` | algo1 | 649900 | 88/120 | 7830/8000 | 0.01 |
| `generated_data_smoke/small_balanced_01.txt` | algo2 | 681700 | 90/120 | 7980/8000 | 3.60 |
| `generated_data_smoke/small_balanced_01.txt` | algo3 | 690400 | 95/120 | 7680/8000 | 82.78 |

## Best By Instance

| Instance | Best Method | Profit | Accepted | Moving | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| `data/instance01.txt` | algo1 | 27900 | 5/5 | 180/180 | 0.01 |
| `data/instance02.txt` | algo2 | 49500 | 9/10 | 1410/1800 | 0.13 |
| `data/instance03.txt` | algo1 | 50000 | 9/10 | 0/0 | 0.00 |
| `data/instance04.txt` | algo2 | 79400 | 16/20 | 5100/5500 | 0.24 |
| `data/instance05.txt` | algo1 | 106800 | 8/10 | 1140/1200 | 0.00 |
| `generated_data_smoke/imbalanced_flow_01.txt` | algo1 | 22192000 | 799/800 | 75060/80000 | 0.16 |
| `generated_data_smoke/large_dense_01.txt` | algo1 | 4946628700 | 10000/10000 | 931080/1000000 | 4.66 |
| `generated_data_smoke/low_level_heavy_01.txt` | algo3 | 2646000 | 283/300 | 24930/25000 | 73.50 |
| `generated_data_smoke/small_balanced_01.txt` | algo3 | 690400 | 95/120 | 7680/8000 | 82.78 |
