# Algo1 / Algo2 / Algo3 / Algo4 Comparison

Per-testcase time limit for timed heuristics: `140s`.

Total benchmark wall time: `2648.19s`.

## Algorithm Summary

- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; each order is inserted into the feasible car route with the smallest extra relocation cost.
- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, then masks selected orders.
- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by `sumR / (1 + sum_move)`; worse full solutions are rolled back.

- **Algo4**: Algo1 plus local IP repair. It samples low-efficiency trajectories, releases those cars, then solves a capped small arc-flow IP over the released cars and candidate unassigned orders.

## Results

| Instance | Algo1 | Algo2 | Algo3 | Algo4 | Best |
| --- | ---: | ---: | ---: | ---: | --- |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance01.txt` | **27900**<br>5/5 orders<br>180/180 move<br>0.01s | **27900**<br>5/5 orders<br>180/180 move<br>0.03s | **27900**<br>5/5 orders<br>180/180 move<br>3.63s | **27900**<br>5/5 orders<br>180/180 move<br>0.00s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance02.txt` | 35100<br>8/10 orders<br>930/1800 move<br>0.00s | **49500**<br>9/10 orders<br>1410/1800 move<br>0.12s | 35100<br>8/10 orders<br>930/1800 move<br>8.04s | 35100<br>8/10 orders<br>930/1800 move<br>1.63s | algo2 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance03.txt` | **50000**<br>9/10 orders<br>0/0 move<br>0.00s | **50000**<br>9/10 orders<br>0/0 move<br>0.01s | **50000**<br>9/10 orders<br>0/0 move<br>1.44s | **50000**<br>9/10 orders<br>0/0 move<br>1.72s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance04.txt` | 36500<br>14/20 orders<br>4110/5500 move<br>0.00s | **79400**<br>16/20 orders<br>5100/5500 move<br>0.23s | 45200<br>15/20 orders<br>3810/5500 move<br>12.15s | 66200<br>16/20 orders<br>5490/5500 move<br>139.98s | algo2 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/data/instance05.txt` | **106800**<br>8/10 orders<br>1140/1200 move<br>0.00s | **106800**<br>8/10 orders<br>1110/1200 move<br>0.12s | **106800**<br>8/10 orders<br>1140/1200 move<br>8.02s | **106800**<br>8/10 orders<br>1140/1200 move<br>1.80s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/imbalanced_flow_01.txt` | 21099000<br>711/800 orders<br>79980/80000 move<br>0.19s | 20073900<br>660/800 orders<br>72330/80000 move<br>140.02s | 21146700<br>721/800 orders<br>79980/80000 move<br>140.09s | **21530400**<br>797/800 orders<br>79950/80000 move<br>140.05s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/imbalanced_flow_02.txt` | 22691700<br>743/800 orders<br>79980/80000 move<br>0.20s | 21474000<br>680/800 orders<br>72660/80000 move<br>140.02s | 22695300<br>748/800 orders<br>79950/80000 move<br>115.68s | **22939200**<br>800/800 orders<br>79980/80000 move<br>140.05s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/large_dense_01.txt` | **5015740900**<br>10000/10000 orders<br>981990/1000000 move<br>4.64s | 4921255300<br>7058/10000 orders<br>945330/1000000 move<br>140.78s | **5015740900**<br>10000/10000 orders<br>981990/1000000 move<br>141.41s | **5015740900**<br>10000/10000 orders<br>981990/1000000 move<br>7.12s | algo1 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/large_dense_02.txt` | 4859493700<br>9999/10000 orders<br>933000/1000000 move<br>4.82s | 4764675400<br>6995/10000 orders<br>913860/1000000 move<br>140.29s | 4859493700<br>9999/10000 orders<br>933000/1000000 move<br>141.34s | **4859685700**<br>10000/10000 orders<br>939600/1000000 move<br>141.66s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/low_level_heavy_01.txt` | 2586400<br>252/300 orders<br>24930/25000 move<br>0.05s | 2776900<br>287/300 orders<br>24390/25000 move<br>37.13s | 2653600<br>270/300 orders<br>24330/25000 move<br>90.31s | **2841100**<br>300/300 orders<br>24930/25000 move<br>139.99s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/low_level_heavy_02.txt` | 2649700<br>270/300 orders<br>24900/25000 move<br>0.04s | 2674900<br>278/300 orders<br>24900/25000 move<br>34.53s | 2656300<br>272/300 orders<br>24060/25000 move<br>73.83s | **2770000**<br>300/300 orders<br>24990/25000 move<br>139.99s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/small_balanced_01.txt` | 504400<br>80/120 orders<br>7920/8000 move<br>0.01s | 481900<br>79/120 orders<br>7260/8000 move<br>4.02s | 523900<br>79/120 orders<br>7440/8000 move<br>69.69s | **578500**<br>90/120 orders<br>7980/8000 move<br>139.96s | algo4 |
| `/Users/yuhungcheng/Documents/Operation Research/Midterm_project/experiments/generated_data_more/small_balanced_02.txt` | 627700<br>86/120 orders<br>7800/8000 move<br>0.01s | 688000<br>92/120 orders<br>7200/8000 move<br>3.65s | 649000<br>94/120 orders<br>7020/8000 move<br>56.14s | **751300**<br>102/120 orders<br>7830/8000 move<br>139.97s | algo4 |
