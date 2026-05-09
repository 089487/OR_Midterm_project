# Algo1 / Algo2 / Algo3 Comparison

Per-testcase time limit for timed heuristics: `140s`.

Total benchmark wall time: `761.31s`.

## Algorithm Summary

- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; each order is inserted into the feasible car route with the smallest extra relocation cost.
- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, then masks selected orders.
- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by `sumR / (1 + sum_move)`; worse full solutions are rolled back.

## Results

| Instance | Algo1 | Algo2 | Algo3 | Best |
| --- | ---: | ---: | ---: | --- |
| `data/instance01.txt` | **27900**<br>5/5 orders<br>180/180 move<br>0.01s | **27900**<br>5/5 orders<br>180/180 move<br>0.03s | **27900**<br>5/5 orders<br>180/180 move<br>3.70s | algo1 |
| `data/instance02.txt` | 35100<br>8/10 orders<br>930/1800 move<br>0.00s | **49500**<br>9/10 orders<br>1410/1800 move<br>0.13s | 35100<br>8/10 orders<br>930/1800 move<br>8.30s | algo2 |
| `data/instance03.txt` | **50000**<br>9/10 orders<br>0/0 move<br>0.00s | **50000**<br>9/10 orders<br>0/0 move<br>0.01s | **50000**<br>9/10 orders<br>0/0 move<br>1.54s | algo1 |
| `data/instance04.txt` | 36500<br>14/20 orders<br>4110/5500 move<br>0.00s | **79400**<br>16/20 orders<br>5100/5500 move<br>0.24s | 45200<br>15/20 orders<br>3810/5500 move<br>12.48s | algo2 |
| `data/instance05.txt` | **106800**<br>8/10 orders<br>1140/1200 move<br>0.00s | **106800**<br>8/10 orders<br>1110/1200 move<br>0.09s | **106800**<br>8/10 orders<br>1140/1200 move<br>7.86s | algo1 |
| `generated_data_smoke/imbalanced_flow_01.txt` | **22192000**<br>799/800 orders<br>75060/80000 move<br>0.16s | 21209200<br>691/800 orders<br>79980/80000 move<br>140.06s | **22192000**<br>799/800 orders<br>75060/80000 move<br>93.62s | algo1 |
| `generated_data_smoke/large_dense_01.txt` | **4946628700**<br>10000/10000 orders<br>931080/1000000 move<br>4.66s | 4858208200<br>7070/10000 orders<br>934890/1000000 move<br>140.15s | **4946628700**<br>10000/10000 orders<br>931080/1000000 move<br>141.42s | algo1 |
| `generated_data_smoke/low_level_heavy_01.txt` | 2639700<br>281/300 orders<br>24990/25000 move<br>0.04s | 2613900<br>280/300 orders<br>24870/25000 move<br>46.39s | **2646000**<br>283/300 orders<br>24930/25000 move<br>73.50s | algo3 |
| `generated_data_smoke/small_balanced_01.txt` | 649900<br>88/120 orders<br>7830/8000 move<br>0.01s | 681700<br>90/120 orders<br>7980/8000 move<br>3.60s | **690400**<br>95/120 orders<br>7680/8000 move<br>82.78s | algo3 |
