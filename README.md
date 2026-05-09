# OR Midterm Project

This repository contains the IP solver, heuristic solvers, public instances, generated test data, and benchmark scripts for the car relocation/order acceptance problem.

## Environment

Use Python 3.12. The project was developed with:

```bash
pip install -r requirements.txt
```


## Repository Layout

| Path | Purpose |
| --- | --- |
| `algorithm_module.py` | Algo1 greedy insertion solver. |
| `heuristic_algo2.py` | Algo2 order-node DP trajectory solver. |
| `heuristic_algo3.py` | Algo3 Algo1 plus local repair solver. |
| `heuristic_algo4.py` | Algo4 Algo1 plus local IP repair solver. |
| `ip_solver.py` | Integer programming solver for public/small instances. |
| `mtp_common.py` | Shared parser, data model, and utilities. |
| `data/` | Public instances `instance01.txt` to `instance05.txt`. |
| `experiments/` | Benchmark scripts, generated smoke tests, and CSV results. |
| `docs/approach.md` | Algorithm explanation, IP model summary, and time complexity. |
| `reference/` | Project statement and related reference PDFs. |

## Generate Test Data

Generate all built-in scenarios:

```bash
python experiments/generate_testcases.py --per-scenario 3
```

By default, files are written to `experiments/generated_data/`.

Generate one case per scenario into a custom directory:

```bash
python experiments/generate_testcases.py \
  --per-scenario 1 \
  --out-dir experiments/generated_data_smoke
```

The generator includes these scenarios:

| Scenario | Scale / Purpose |
| --- | --- |
| `small_balanced` | Small balanced case. |
| `low_level_heavy` | More low-level demand, tests upgrade usage. |
| `imbalanced_flow` | Pick-up and return stations follow different distributions. |
| `large_dense` | Maximum-scale stress case. |

## Run Benchmarks

Compare Algo1, Algo2, Algo3, and Algo4 on the five public instances plus generated smoke data:

```bash
python experiments/benchmark_algorithms.py
```

Useful options:

```bash
python experiments/benchmark_algorithms.py \
  --generated-dir experiments/generated_data_smoke \
  --time-limit 140 \
  --algo4-candidate-order-limit 160 \
  --algo4-per-ip-seconds 0.5 \
  --algo4-max-no-improve 0 \
  --out-dir experiments/benchmark_results
```

Benchmark only selected instances:

```bash
python experiments/benchmark_algorithms.py \
  data/instance01.txt data/instance04.txt
```

Outputs:

| File | Content |
| --- | --- |
| `experiments/benchmark_results/algo1234_comparison.csv` | Raw comparison table. |
| `experiments/benchmark_results/algo1234_comparison.md` | Markdown summary table. |

## Run IP vs Heuristic Smoke Benchmark

This script compares IP, Algo1, and Algo2. IP is only attempted for public and small generated cases.

```bash
python experiments/benchmark_heuristics.py \
  --ip-time-limit 30 \
  --algo2-seconds 30
```

## Lambda Experiments

Run Algo2 over the fixed lambda list:

```bash
python experiments/lambda_benchmark.py \
  --max-seconds 1800 \
  --out-dir experiments/benchmark_results
```

Run ternary search over lambda in `[0, 1]`:

```bash
python experiments/algo2_trisearch.py \
  --iterations 20 \
  --max-seconds 1800 \
  --out-dir experiments/benchmark_results
```

## Algorithm Details

See `docs/approach.md` for the IP formulation, Algo1/Algo2/Algo3 descriptions, complexity analysis, and benchmark summary.
