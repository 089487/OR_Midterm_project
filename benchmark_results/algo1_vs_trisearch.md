# Algo1 vs Algo2 Ternary Search

Algo1 was run with `raw_test=True`, so no small-case IP fallback is included. Algo2 numbers use the best lambda found by `algo2_trisearch.py` with 20 ternary-search iterations in `[0, 1]`.

| Instance | Algo1 Profit | Trisearch Profit | Delta | Algo1 Accepted | Trisearch Accepted | Algo1 Moving | Trisearch Moving | Algo1 Time | Trisearch Time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `instance01` | 27,900 | 27,900 | 0 | 5/5 | 5/5 | 180/180 | 180/180 | 0.0080s | 0.16s |
| `instance02` | 35,100 | 49,500 | +14,400 | 8/10 | 9/10 | 930/1800 | 1410/1800 | 0.0019s | 0.53s |
| `instance03` | 50,000 | 50,000 | 0 | 9/10 | 9/10 | 0/0 | 0/0 | 0.0005s | 0.05s |
| `instance04` | 36,500 | 79,400 | +42,900 | 14/20 | 16/20 | 4110/5500 | 4680/5500 | 0.0025s | 1.02s |
| `instance05` | 106,800 | 102,300 | -4,500 | 8/10 | 7/10 | 1140/1200 | 1050/1200 | 0.0011s | 0.40s |
| `small_balanced_01` | 649,900 | 720,400 | +70,500 | 88/120 | 93/120 | 7830/8000 | 7980/8000 | 0.0096s | 13.29s |
| `low_level_heavy_01` | 2,639,700 | 2,636,400 | -3,300 | 281/300 | 284/300 | 24990/25000 | 24690/25000 | 0.0387s | 107.11s |
| `imbalanced_flow_01` | 22,192,000 | 21,398,500 | -793,500 | 799/800 | 702/800 | 75060/80000 | 79830/80000 | 0.1648s | 481.45s |
| `large_dense_01` | 4,946,628,700 | 4,875,626,200 | -71,002,500 | 10000/10000 | 7340/10000 | 931080/1000000 | 999390/1000000 | 5.1293s | 953.60s |

Takeaway: Algo2 ternary search improves the harder public instances and `small_balanced_01`, but Algo1 is still better on the generated dense/imbalanced cases and is dramatically faster. The current best practical wrapper should still keep Algo1 as a baseline and let Algo2 replace it only when its profit is higher.
