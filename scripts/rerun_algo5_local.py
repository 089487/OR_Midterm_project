from __future__ import annotations

import argparse
import importlib
import time
from pathlib import Path

from mtp_common import parse_instance
from run_algo_parallel import is_accepted, profit, scenario_sort_key, upsert, validate


def run_algo5(instance_path: Path) -> dict[str, object]:
    inst = parse_instance(instance_path)
    func = getattr(importlib.import_module("algo5"), "heuristic_algorithm")
    start = time.perf_counter()
    try:
        assignment, _ = func(str(instance_path), raw_test=True)
        seconds = time.perf_counter() - start
        feasible, moving, violations = validate(inst, assignment)
        return {
            "instance": instance_path.name,
            "algorithm": "algo5",
            "moving_time": moving,
            "profit": profit(inst, assignment),
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": sum(1 for car_id in assignment if is_accepted(car_id)),
            "status": "ok" if feasible else "infeasible",
            "error": "" if feasible else "; ".join(violations[:5]),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "algorithm": "algo5",
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/exp_instances")
    args = parser.parse_args()

    root = Path(args.root)
    scenarios = sorted(
        [path for path in root.iterdir() if path.is_dir() and path.name.startswith("S")],
        key=scenario_sort_key,
    )
    total_jobs = sum(1 for scenario_dir in scenarios for _ in scenario_dir.glob("*.txt"))
    done = 0
    print(f"rerun algo5 root={root} scenarios={len(scenarios)} instances={total_jobs}", flush=True)
    for scenario_dir in scenarios:
        instances = sorted(scenario_dir.glob("*.txt"))
        print(f"{scenario_dir.name}: start {len(instances)} instances", flush=True)
        for idx, instance_path in enumerate(instances, start=1):
            row = run_algo5(instance_path)
            upsert(scenario_dir / "benchmark_results.csv", row)
            done += 1
            print(
                f"[{done}/{total_jobs}] {scenario_dir.name} [{idx}/{len(instances)}] "
                f"{row['status']} {row['instance']} seconds={row['execution_time']} "
                f"profit={row['profit']} moving_time={row['moving_time']}",
                flush=True,
            )
        print(f"{scenario_dir.name}: done", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
