# Algo3 Batch Ratio Repair Comparison

Algo3 starts from Algo1 raw, then runs batch trajectory repair. In each iteration it samples up to five existing trajectories using inverse softmax on trajectory efficiency, where efficiency is `reward / (1 + route_move_time)`. Those five routes are released together, the selected cars are shuffled, and each car is rebuilt with the top-10 station sweep DP. The single-car DP score is also `sum(reward) / (1 + sum(move_time))`, so there is no inner lambda loop. A lower-profit full solution is rolled back; equal-profit moves are accepted to allow movement on plateaus.

Configuration: `seed=1142`, `temperature=0.35`, `batch_size=5`, `max_seconds=100`.

Total benchmark time across public plus generated smoke cases: 419.39s.

| Instance | Algo1 Profit | Algo3 Profit | Delta | Algo1 Accepted | Algo3 Accepted | Algo1 Moving | Algo3 Moving | Algo1 Time | Algo3 Time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `instance01` | 27,900 | 27,900 | 0 | 5/5 | 5/5 | 180/180 | 180/180 | 0.0280s | 4.6305s |
| `instance02` | 35,100 | 35,100 | 0 | 8/10 | 8/10 | 930/1800 | 930/1800 | 0.0018s | 12.2563s |
| `instance03` | 50,000 | 50,000 | 0 | 9/10 | 9/10 | 0/0 | 0/0 | 0.0007s | 2.1312s |
| `instance04` | 36,500 | 45,200 | +8,700 | 14/20 | 15/20 | 4110/5500 | 3810/5500 | 0.0025s | 17.7047s |
| `instance05` | 106,800 | 106,800 | 0 | 8/10 | 8/10 | 1140/1200 | 1140/1200 | 0.0017s | 12.4179s |
| `small_balanced_01` | 649,900 | 690,400 | +40,500 | 88/120 | 95/120 | 7830/8000 | 7680/8000 | 0.0173s | 71.4847s |
| `low_level_heavy_01` | 2,639,700 | 2,646,000 | +6,300 | 281/300 | 283/300 | 24990/25000 | 24930/25000 | 0.0477s | 88.1066s |
| `imbalanced_flow_01` | 22,192,000 | 22,192,000 | 0 | 799/800 | 799/800 | 75060/80000 | 75060/80000 | 0.2320s | 100.1009s |
| `large_dense_01` | 4,946,628,700 | 4,946,628,700 | 0 | 10000/10000 | 10000/10000 | 931080/1000000 | 931080/1000000 | 7.7223s | 102.0565s |

Takeaway: batch ratio repair is weaker on `instance04` than the lambda-DP random versions, but it gives the best Algo3 results so far on `small_balanced_01` and `low_level_heavy_01`. Removing the lambda loop makes each repair attempt cheaper, but the ratio DP is more conservative on public04.
