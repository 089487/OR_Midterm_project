# Algo1 / Algo2 / Algo3 / Algo4 Comparison

Per-testcase time limit for timed heuristics: `140s`.

Total benchmark wall time: `1279.54s`.

## Algorithm Summary

- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; each order is inserted into the feasible car route with the smallest extra relocation cost.
- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, then masks selected orders.
- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by `sumR / (1 + sum_move)`; worse full solutions are rolled back.

- **Algo4**: Algo1 plus local IP repair. It samples low-efficiency trajectories, releases those cars, then solves a capped small arc-flow IP over the released cars and candidate unassigned orders.

## Results

| Instance | Algo1 | Algo2 | Algo3 | Algo4 | Best |
| --- | ---: | ---: | ---: | ---: | --- |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance01.txt` | **27900**<br>5/5 orders<br>180/180 move<br>0.01s | **27900**<br>5/5 orders<br>180/180 move<br>0.03s | **27900**<br>5/5 orders<br>180/180 move<br>3.92s | **27900**<br>5/5 orders<br>180/180 move<br>0.00s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance02.txt` | 35100<br>8/10 orders<br>930/1800 move<br>0.00s | **49500**<br>9/10 orders<br>1410/1800 move<br>0.16s | 35100<br>8/10 orders<br>930/1800 move<br>10.20s | 35100<br>8/10 orders<br>930/1800 move<br>2.53s | algo2 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance03.txt` | **50000**<br>9/10 orders<br>0/0 move<br>0.00s | **50000**<br>9/10 orders<br>0/0 move<br>0.01s | **50000**<br>9/10 orders<br>0/0 move<br>1.70s | **50000**<br>9/10 orders<br>0/0 move<br>2.41s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance04.txt` | 36500<br>14/20 orders<br>4110/5500 move<br>0.01s | **79400**<br>16/20 orders<br>5100/5500 move<br>0.42s | 45200<br>15/20 orders<br>3810/5500 move<br>12.54s | 66200<br>16/20 orders<br>5490/5500 move<br>139.95s | algo2 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance05.txt` | **106800**<br>8/10 orders<br>1140/1200 move<br>0.00s | **106800**<br>8/10 orders<br>1110/1200 move<br>0.10s | **106800**<br>8/10 orders<br>1140/1200 move<br>7.91s | **106800**<br>8/10 orders<br>1140/1200 move<br>2.88s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_smoke/imbalanced_flow_01.txt` | **22192000**<br>799/800 orders<br>75060/80000 move<br>0.26s | 21209200<br>691/800 orders<br>79980/80000 move<br>140.04s | **22192000**<br>799/800 orders<br>75060/80000 move<br>95.61s | **22192000**<br>799/800 orders<br>75060/80000 move<br>140.06s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_smoke/large_dense_01.txt` | **4946628700**<br>10000/10000 orders<br>931080/1000000 move<br>4.77s | 4858208200<br>7070/10000 orders<br>934890/1000000 move<br>140.77s | **4946628700**<br>10000/10000 orders<br>931080/1000000 move<br>142.01s | **4946628700**<br>10000/10000 orders<br>931080/1000000 move<br>6.98s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_smoke/low_level_heavy_01.txt` | 2639700<br>281/300 orders<br>24990/25000 move<br>0.05s | 2613900<br>280/300 orders<br>24870/25000 move<br>35.08s | 2646000<br>283/300 orders<br>24930/25000 move<br>59.62s | **2694600**<br>300/300 orders<br>24960/25000 move<br>139.98s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_smoke/small_balanced_01.txt` | 649900<br>88/120 orders<br>7830/8000 move<br>0.01s | 681700<br>90/120 orders<br>7980/8000 move<br>3.60s | 690400<br>95/120 orders<br>7680/8000 move<br>45.16s | **812500**<br>99/120 orders<br>7980/8000 move<br>139.97s | algo4 |
