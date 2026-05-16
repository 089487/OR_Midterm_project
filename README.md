# OR Midterm Project

This repository contains the final submission, the main algorithm code, and the
experimental artifacts for the IEDO car rental order-acceptance and relocation
problem.

## Layout

| Path | Purpose |
| --- | --- |
| `Submit/` | Final submitted report and `algorithm_module.py`. |
| `code/` | Main algorithm files kept for review and comparison. |
| `data/exp_instances/` | 14-scenario experiment dataset and benchmark outputs. |
| `data/scenario_study_128/` | Larger robustness scenario study and summary plots. |
| `data/public_plans/` | Optimal plans for the public instances. |
| `docs/experiment.md` | Experiment design and benchmark interpretation. |
| `docs/approach.md` | Algorithm design summary. |
| `scripts/` | Generation, benchmarking, plotting, and helper scripts. |
| `reference/` | Project statement, related papers, example code, and report sources. |

`MTP_lib.py` is kept at the repository root and duplicated in `code/` and
`scripts/` as a compatibility support library for the course-provided import
style. The final course submission is `Submit/algorithm_module.py`.

## Main Code

The reviewed algorithm files are:

| File | Notes |
| --- | --- |
| `code/algorithm_naive.py` | Naive baseline used in scenario studies. |
| `code/algorithm_module.py` | Full local-development algorithm module. |
| `code/algorithm_module_no_other_library.py` | Submission-oriented module using only `MTP_lib` plus built-in logic. |
| `code/MTP_lib.py` | Compatibility copy of the course helper library. |

`code/algorithm_module_no_other_library.py` uses a global time budget in
`heuristic_algorithm()`. Its pre-build phase caps the internal Algo5 heuristic
at 30 seconds, then gives the remaining time to the local improvement phase.

## Environment

Use Python 3.12+.

```bash
python3 -m pip install -r requirements.txt
```

`gurobipy` is needed for the IP solver and the local-IP improvement scripts. If
Gurobi is unavailable, the final heuristic module falls back to its pre-built
solution instead of failing the whole run.

## Data

`data/exp_instances/` contains the main 14-scenario experiment:

- 14 scenarios, `S1` through `S14`
- 30 instances per scenario
- IP plans under `data/exp_instances/S*/plan/`
- per-scenario benchmark CSVs under `data/exp_instances/S*/benchmark_results.csv`
- summary outputs under `data/exp_instances/summary/`

`data/scenario_study_128/` contains the larger scenario study:

- generated study instances for selected difficult scenarios
- `scenario_gap_summary.csv`
- per-scenario optimal-gap histograms
- `optimal_gap_histograms_combined.svg`

The original course data archive is kept at
`data/OR114-2_midtermProject_data.zip`.

## Scripts

Common commands from the repository root:

```bash
# Regenerate the 14-scenario experiment dataset.
python3 scripts/generate_code.py

# Solve generated instances with the IP solver.
python3 scripts/run_all_ip_solver.py --root data/exp_instances

# Run benchmark rows for selected solver modules.
python3 scripts/run_algorithm_benchmarks.py \
  --root data/exp_instances \
  --solver scripts/algo1.py \
  --solver scripts/algo5.py

# Run parallel scenario benchmarks.
python3 scripts/run_algo_parallel.py \
  --root data/exp_instances \
  --max-seconds 10 \
  --jobs 14

# Summarize benchmark CSVs.
python3 scripts/summarize_benchmarks.py \
  --root data/exp_instances \
  --out-dir data/exp_instances/summary

# Run the larger scenario study.
python3 scripts/run_scenario_study.py

# Generate the report table from benchmark summaries.
python3 scripts/generate_project_table3.py
```

The legacy solver modules that these scripts use are also in `scripts/`.

## Documentation

- `docs/approach.md` explains the main algorithmic ideas: the greedy baseline,
  demand-aware pre-build heuristic, and final local-IP optimization.
- `docs/experiment.md` explains the 14-scenario design and the executed
  benchmark outputs.

Report source files and duplicate historical plots were moved out of `docs/`
and into `reference/report_sources/` so `docs/` stays focused.
