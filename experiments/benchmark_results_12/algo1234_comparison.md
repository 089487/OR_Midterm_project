# Algo1 / Algo2 / Algo3 / Algo4 Comparison

Per-testcase time limit for timed heuristics: `140s`.

Total benchmark wall time: `3810.45s`.

## Algorithm Summary

- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; each order is inserted into the feasible car route with the smallest extra relocation cost.
- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, then masks selected orders.
- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by `sumR / (1 + sum_move)`; worse full solutions are rolled back.

- **Algo4**: Algo1 plus local IP repair. It samples low-efficiency trajectories, releases those cars, then solves a capped small arc-flow IP over the released cars and candidate unassigned orders.

## Results

| Instance | Algo1 | Algo2 | Algo3 | Algo4 | Best |
| --- | ---: | ---: | ---: | ---: | --- |
| `./data/instance01.txt` | **27900**<br>5/5 orders<br>180/180 move<br>0.01s | **27900**<br>5/5 orders<br>180/180 move<br>0.03s | **27900**<br>5/5 orders<br>180/180 move<br>3.96s | **27900**<br>5/5 orders<br>180/180 move<br>0.00s | algo4 |
| `./data/instance02.txt` | 35100<br>8/10 orders<br>930/1800 move<br>0.00s | **49500**<br>9/10 orders<br>1410/1800 move<br>0.13s | 35100<br>8/10 orders<br>930/1800 move<br>8.17s | 35100<br>8/10 orders<br>930/1800 move<br>1.58s | algo2 |
| `./data/instance03.txt` | **50000**<br>9/10 orders<br>0/0 move<br>0.00s | **50000**<br>9/10 orders<br>0/0 move<br>0.01s | **50000**<br>9/10 orders<br>0/0 move<br>1.44s | **50000**<br>9/10 orders<br>0/0 move<br>2.10s | algo1 |
| `./data/instance04.txt` | 36500<br>14/20 orders<br>4110/5500 move<br>0.00s | **79400**<br>16/20 orders<br>5100/5500 move<br>0.25s | 45200<br>15/20 orders<br>3810/5500 move<br>12.31s | 66200<br>16/20 orders<br>5490/5500 move<br>139.95s | algo2 |
| `./data/instance05.txt` | **106800**<br>8/10 orders<br>1140/1200 move<br>0.00s | **106800**<br>8/10 orders<br>1110/1200 move<br>0.10s | **106800**<br>8/10 orders<br>1140/1200 move<br>8.08s | **106800**<br>8/10 orders<br>1140/1200 move<br>2.00s | algo1 |
| `./experiments/generated_data_12/imbalanced_flow_01.txt` | 23729700<br>784/800 orders<br>79950/80000 move<br>0.18s | 22965300<br>724/800 orders<br>79980/80000 move<br>140.06s | 23729700<br>784/800 orders<br>79950/80000 move<br>103.66s | **23751300**<br>799/800 orders<br>79890/80000 move<br>140.08s | algo4 |
| `./experiments/generated_data_12/imbalanced_flow_02.txt` | **21948800**<br>800/800 orders<br>71760/80000 move<br>0.28s | 21184700<br>711/800 orders<br>72120/80000 move<br>140.05s | **21948800**<br>800/800 orders<br>71760/80000 move<br>91.77s | **21948800**<br>800/800 orders<br>71760/80000 move<br>0.32s | algo1 |
| `./experiments/generated_data_12/imbalanced_flow_03.txt` | 21289400<br>637/800 orders<br>79890/80000 move<br>0.15s | 20465300<br>641/800 orders<br>73800/80000 move<br>140.04s | 21465500<br>664/800 orders<br>79860/80000 move<br>140.17s | **22281800**<br>708/800 orders<br>79980/80000 move<br>140.06s | algo4 |
| `./experiments/generated_data_12/large_dense_01.txt` | **4845310300**<br>9999/10000 orders<br>992790/1000000 move<br>5.48s | 3651407200<br>6869/10000 orders<br>999990/1000000 move<br>140.17s | **4845310300**<br>9999/10000 orders<br>992790/1000000 move<br>141.40s | **4845310300**<br>9999/10000 orders<br>992790/1000000 move<br>141.57s | algo1 |
| `./experiments/generated_data_12/large_dense_02.txt` | 4894638400<br>9999/10000 orders<br>999990/1000000 move<br>6.39s | 4794449200<br>7010/10000 orders<br>941430/1000000 move<br>141.68s | 4894638400<br>9999/10000 orders<br>999990/1000000 move<br>141.53s | **4894638700**<br>10000/10000 orders<br>999990/1000000 move<br>141.41s | algo4 |
| `./experiments/generated_data_12/large_dense_03.txt` | 4955124700<br>9832/10000 orders<br>999990/1000000 move<br>4.54s | 4848996100<br>6948/10000 orders<br>973380/1000000 move<br>140.16s | 4955124700<br>9832/10000 orders<br>999990/1000000 move<br>141.27s | **4955396200**<br>9926/10000 orders<br>999960/1000000 move<br>141.58s | algo4 |
| `./experiments/generated_data_12/low_level_heavy_01.txt` | 2704000<br>288/300 orders<br>24960/25000 move<br>0.05s | 2602300<br>268/300 orders<br>20430/25000 move<br>30.55s | 2704000<br>288/300 orders<br>24960/25000 move<br>52.15s | **2713900**<br>300/300 orders<br>24930/25000 move<br>139.99s | algo4 |
| `./experiments/generated_data_12/low_level_heavy_02.txt` | 2111900<br>274/300 orders<br>24630/25000 move<br>0.04s | 2111300<br>280/300 orders<br>21360/25000 move<br>40.46s | 2113400<br>274/300 orders<br>24360/25000 move<br>77.53s | **2199200**<br>300/300 orders<br>24870/25000 move<br>139.98s | algo4 |
| `./experiments/generated_data_12/low_level_heavy_03.txt` | 2770900<br>285/300 orders<br>24900/25000 move<br>0.05s | 2763100<br>282/300 orders<br>24990/25000 move<br>30.22s | 2770900<br>285/300 orders<br>24900/25000 move<br>56.68s | **2815900**<br>300/300 orders<br>24870/25000 move<br>139.98s | algo4 |
| `./experiments/generated_data_12/small_balanced_01.txt` | 609200<br>93/120 orders<br>7980/8000 move<br>0.02s | 606800<br>89/120 orders<br>7500/8000 move<br>3.67s | 609200<br>93/120 orders<br>7980/8000 move<br>47.13s | **694700**<br>105/120 orders<br>7980/8000 move<br>139.96s | algo4 |
| `./experiments/generated_data_12/small_balanced_02.txt` | 571000<br>83/120 orders<br>7800/8000 move<br>0.01s | 533800<br>86/120 orders<br>6390/8000 move<br>3.63s | 571000<br>83/120 orders<br>7800/8000 move<br>50.55s | **639700**<br>92/120 orders<br>7980/8000 move<br>140.00s | algo4 |
| `./experiments/generated_data_12/small_balanced_03.txt` | 549600<br>80/120 orders<br>7980/8000 move<br>0.02s | 577800<br>88/120 orders<br>7830/8000 move<br>4.99s | 558900<br>81/120 orders<br>7830/8000 move<br>66.42s | **667800**<br>91/120 orders<br>7920/8000 move<br>139.97s | algo4 |
