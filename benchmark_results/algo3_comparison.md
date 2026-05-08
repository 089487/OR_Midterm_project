# Algo3 Comparison

Algo3 starts from Algo1 raw, then runs release-one-car local search until no useful level remains or the 100-second cap is reached. In each iteration it selects the rejected-order level with the largest total revenue, releases the weakest compatible car route, and rebuilds that single car with the top-10 station sweep DP over the released plus currently rejected orders. If a level rebuild returns the same route or does not improve profit, that level is skipped in later iterations.

Total benchmark time across public plus generated smoke cases: 16.58s.

| Instance | Algo1 Profit | Algo3 Profit | Delta | Algo1 Accepted | Algo3 Accepted | Algo1 Moving | Algo3 Moving | Algo1 Time | Algo3 Time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `instance01` | 27,900 | 27,900 | 0 | 5/5 | 5/5 | 180/180 | 180/180 | 0.0109s | 0.0009s |
| `instance02` | 35,100 | 35,100 | 0 | 8/10 | 8/10 | 930/1800 | 930/1800 | 0.0014s | 0.0025s |
| `instance03` | 50,000 | 50,000 | 0 | 9/10 | 9/10 | 0/0 | 0/0 | 0.0004s | 0.0006s |
| `instance04` | 36,500 | 45,200 | +8,700 | 14/20 | 15/20 | 4110/5500 | 4440/5500 | 0.0021s | 0.0051s |
| `instance05` | 106,800 | 106,800 | 0 | 8/10 | 8/10 | 1140/1200 | 1140/1200 | 0.0012s | 0.0021s |
| `small_balanced_01` | 649,900 | 664,300 | +14,400 | 88/120 | 92/120 | 7830/8000 | 7980/8000 | 0.0107s | 0.0229s |
| `low_level_heavy_01` | 2,639,700 | 2,639,700 | 0 | 281/300 | 281/300 | 24990/25000 | 24990/25000 | 0.0538s | 0.0735s |
| `imbalanced_flow_01` | 22,192,000 | 22,192,000 | 0 | 799/800 | 799/800 | 75060/80000 | 75060/80000 | 0.1882s | 0.2441s |
| `large_dense_01` | 4,946,628,700 | 4,946,628,700 | 0 | 10000/10000 | 10000/10000 | 931080/1000000 | 931080/1000000 | 4.7890s | 10.7682s |

Takeaway: Algo3 is a cheap local improvement on top of Algo1. It currently improves `instance04` and `small_balanced_01`, never worsens the tested instances, and remains far under the 100-second cap on the current benchmark. The improvement is limited on dense generated cases because Algo1 already accepts nearly all orders there.
