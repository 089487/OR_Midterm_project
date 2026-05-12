from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from pathlib import Path

from ip_solver import solve_instance, write_plan


STOP_REQUESTED = False


def _request_stop(signum, frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"\nreceived signal {signum}; stopping after the current instance...", flush=True)


def _instance_paths(root: Path, scenarios: list[str] | None) -> list[Path]:
    if scenarios:
        paths: list[Path] = []
        for scenario in scenarios:
            scenario_dir = root / scenario
            paths.extend(sorted(scenario_dir.glob("*.txt")))
        return paths
    return sorted(root.glob("S*/*.txt"))


def _log_row(log_path: Path, row: dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    exists = log_path.exists()
    fieldnames = [
        "timestamp",
        "instance",
        "plan",
        "status",
        "seconds",
        "accepted_sales",
        "profit",
        "error",
    ]
    with log_path.open("a", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _run_time_row_path(instance_path: Path) -> Path:
    return instance_path.parent / "run_time.csv"


def _append_run_time(instance_path: Path, row: dict[str, object]) -> None:
    path = _run_time_row_path(instance_path)
    fieldnames = [
        "instance",
        "plan",
        "status",
        "seconds",
        "accepted_sales",
        "profit",
        "error",
        "timestamp",
    ]
    rows: list[dict[str, object]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fp:
            rows = list(csv.DictReader(fp))

    row_by_instance = {str(existing.get("instance", "")): existing for existing in rows}
    row_by_instance[str(row.get("instance", ""))] = {name: row.get(name, "") for name in fieldnames}

    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row_by_instance.values())


def _previous_ok_row(log_path: Path, instance_path: Path) -> dict[str, object] | None:
    if not log_path.exists():
        return None
    with log_path.open(newline="", encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            if row.get("instance") == str(instance_path) and row.get("status") == "ok":
                return row
    return None


def run_all(
    root: Path,
    scenarios: list[str] | None = None,
    time_limit: int | None = None,
    force: bool = False,
    log_path: Path | None = None,
) -> None:
    paths = _instance_paths(root, scenarios)
    if not paths:
        raise FileNotFoundError(f"no instance .txt files found under {root}")

    log_path = log_path or root / "ip_solver_run_log.csv"
    total = len(paths)
    print(f"found {total} instances under {root}", flush=True)

    for idx, instance_path in enumerate(paths, start=1):
        plan_dir = instance_path.parent / "plan"
        plan_path = plan_dir / f"{instance_path.stem}_optimal_plan.txt"

        if STOP_REQUESTED:
            print("stop requested; exiting before starting next instance.", flush=True)
            break

        if plan_path.exists() and plan_path.stat().st_size > 0 and not force:
            print(f"[{idx}/{total}] skip existing {plan_path}", flush=True)
            previous_row = _previous_ok_row(log_path, instance_path)
            if previous_row is None:
                previous_row = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "instance": str(instance_path),
                    "plan": str(plan_path),
                    "status": "skipped_existing",
                    "seconds": "",
                    "accepted_sales": "",
                    "profit": "",
                    "error": "",
                }
            _append_run_time(instance_path, previous_row)
            continue

        plan_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{idx}/{total}] solving {instance_path} -> {plan_path}", flush=True)
        start = time.perf_counter()
        try:
            solution = solve_instance(instance_path, time_limit=time_limit, verbose=False)
            write_plan(solution, plan_path)
            seconds = time.perf_counter() - start
            row = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "instance": str(instance_path),
                "plan": str(plan_path),
                "status": "ok",
                "seconds": f"{seconds:.3f}",
                "accepted_sales": solution["objective"],
                "profit": solution["profit"],
                "error": "",
            }
            _log_row(log_path, row)
            _append_run_time(instance_path, row)
            print(
                f"[{idx}/{total}] ok {instance_path.name}: "
                f"accepted_sales={solution['objective']} profit={solution['profit']} "
                f"seconds={seconds:.1f}",
                flush=True,
            )
        except KeyboardInterrupt:
            seconds = time.perf_counter() - start
            row = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "instance": str(instance_path),
                "plan": str(plan_path),
                "status": "interrupted",
                "seconds": f"{seconds:.3f}",
                "accepted_sales": "",
                "profit": "",
                "error": "KeyboardInterrupt",
            }
            _log_row(log_path, row)
            _append_run_time(instance_path, row)
            print("interrupted; current incomplete instance can be rerun later.", flush=True)
            raise
        except Exception as exc:
            seconds = time.perf_counter() - start
            row = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "instance": str(instance_path),
                "plan": str(plan_path),
                "status": "error",
                "seconds": f"{seconds:.3f}",
                "accepted_sales": "",
                "profit": "",
                "error": f"{type(exc).__name__}: {exc}",
            }
            _log_row(log_path, row)
            _append_run_time(instance_path, row)
            print(f"[{idx}/{total}] error {instance_path}: {type(exc).__name__}: {exc}", flush=True)

    print("runner finished.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ip_solver on all exp instances and write per-folder plans.")
    parser.add_argument("--root", default="data/exp_instances", help="root containing S*/ instance folders")
    parser.add_argument("--scenario", action="append", help="run only one scenario folder; can be repeated")
    parser.add_argument("--time-limit", type=int, default=None, help="optional Gurobi time limit per instance")
    parser.add_argument("--force", action="store_true", help="rerun instances even if plan already exists")
    parser.add_argument("--log", default=None, help="CSV log path; defaults to <root>/ip_solver_run_log.csv")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    try:
        run_all(
            root=Path(args.root),
            scenarios=args.scenario,
            time_limit=args.time_limit,
            force=args.force,
            log_path=Path(args.log) if args.log else None,
        )
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
