from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Iterable

from mtp_common import (
    Instance,
    can_serve_level,
    latest_arrival_for_pickup,
    order_ready_minute,
    parse_instance,
)


RESULT_FIELDS = [
    "instance",
    "algorithm",
    "moving_time",
    "profit",
    "execution_time",
    "accepted_orders",
    "accepted_sales",
    "status",
    "error",
    "timestamp",
]
IP_FIELDS = [
    "instance",
    "plan",
    "status",
    "seconds",
    "accepted_sales",
    "profit",
    "moving_time",
    "accepted_orders",
    "error",
    "timestamp",
]
PIPELINE_ALGORITHMS = ("algo_naive", "algo_union")


def _make_executor(workers: int):
    try:
        return ProcessPoolExecutor(max_workers=workers)
    except PermissionError:
        print("process pool unavailable; falling back to a thread pool", flush=True)
        return ThreadPoolExecutor(max_workers=1)


def benchmark_local(
    directory_path: str | Path,
    python_files: Iterable[str | Path],
    output_csv: str | Path | None = None,
    raw_test: bool = False,
) -> Path:
    """Run solver Python files on every .txt instance in a directory.

    Each solver file is expected to define:
        heuristic_algorithm(instance_path, raw_test) -> (assignment, relocation)

    The CSV contains one row per (instance, algorithm).
    """
    instance_dir = Path(directory_path)
    if not instance_dir.is_dir():
        raise NotADirectoryError(f"directory_path does not exist: {instance_dir}")

    solvers = [_load_solver(Path(python_file)) for python_file in python_files]
    instance_files = sorted(instance_dir.glob("*.txt"))
    if not instance_files:
        raise FileNotFoundError(f"no .txt instances found in {instance_dir}")

    csv_path = Path(output_csv) if output_csv is not None else instance_dir / "benchmark_results.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for instance_file in instance_files:
        inst = parse_instance(instance_file)
        for solver_path, module in solvers:
            row = _run_one_solver(inst, instance_file, solver_path, module, raw_test)
            rows.append(row)

    fieldnames = [
        "instance",
        "algorithm",
        "moving_time",
        "profit",
        "execution_time",
        "accepted_orders",
        "status",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def _load_solver(python_file: Path) -> tuple[Path, ModuleType]:
    solver_path = python_file.resolve()
    if not solver_path.is_file():
        raise FileNotFoundError(f"solver file does not exist: {solver_path}")

    module_name = f"_benchmark_solver_{solver_path.stem}_{abs(hash(solver_path))}"
    spec = importlib.util.spec_from_file_location(module_name, solver_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import solver from {solver_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "heuristic_algorithm"):
        raise AttributeError(f"{solver_path} does not define heuristic_algorithm(instance_path)")
    return solver_path, module


def _run_one_solver(inst: Instance, instance_file: Path, solver_path: Path, module: ModuleType, raw_test: bool = False) -> dict[str, object]:
    start = time.perf_counter()
    try:
        assignment, relocation = module.heuristic_algorithm(str(instance_file), raw_test=raw_test)
        execution_time = time.perf_counter() - start
        moving_time = _moving_time(inst, relocation)
        profit = _profit(inst, assignment)
        accepted_orders = sum(1 for car_id in assignment if _is_accepted(car_id))
        return {
            "instance": instance_file.name,
            "algorithm": solver_path.stem,
            "moving_time": moving_time,
            "profit": profit,
            "execution_time": f"{execution_time:.6f}",
            "accepted_orders": accepted_orders,
            "status": "ok",
            "error": "",
        }
    except Exception as exc:
        execution_time = time.perf_counter() - start
        return {
            "instance": instance_file.name,
            "algorithm": solver_path.stem,
            "moving_time": "",
            "profit": "",
            "execution_time": f"{execution_time:.6f}",
            "accepted_orders": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _is_accepted(car_id: object) -> bool:
    return car_id is not None and int(car_id) > 0


def _profit(inst: Instance, assignment: Iterable[object]) -> int:
    accepted_revenue = sum(
        order.revenue
        for order, car_id in zip(inst.orders, assignment)
        if _is_accepted(car_id)
    )
    total_revenue = sum(order.revenue for order in inst.orders)
    rejected_revenue = total_revenue - accepted_revenue
    return accepted_revenue - 2 * rejected_revenue


def _moving_time(inst: Instance, relocation: Iterable[list]) -> int:
    total = 0
    for row in relocation:
        if len(row) >= 6:
            try:
                total += int(row[5])
                continue
            except (TypeError, ValueError):
                pass
        if len(row) >= 3:
            total += inst.move_time[(int(row[1]), int(row[2]))]
    return total


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _write_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])


def _upsert(path: Path, row: dict[str, object], fieldnames: list[str], key_fields: tuple[str, ...]) -> None:
    rows = _read_rows(path)
    by_key = {tuple(str(existing.get(field, "")) for field in key_fields): existing for existing in rows}
    key = tuple(str(row.get(field, "")) for field in key_fields)
    by_key[key] = row
    ordered = sorted(by_key.values(), key=lambda item: tuple(str(item.get(field, "")) for field in key_fields))
    _write_rows(path, ordered, fieldnames)


def _existing_ok(path: Path, key_fields: tuple[str, ...], key: tuple[str, ...]) -> bool:
    for row in _read_rows(path):
        if tuple(row.get(field, "") for field in key_fields) == key and row.get("status") == "ok":
            return True
    return False


def _accepted_sales(inst: Instance, assignment: Iterable[object]) -> int:
    return sum(order.revenue for order, car_id in zip(inst.orders, assignment) if _is_accepted(car_id))


def _validate_assignment(inst: Instance, assignment: Iterable[object]) -> tuple[bool, int, list[str]]:
    cars = {car.id: car for car in inst.cars}
    orders = {order.id: order for order in inst.orders}
    by_car = {car.id: [] for car in inst.cars}
    violations: list[str] = []

    for order_id, car_id in enumerate(assignment, start=1):
        if not _is_accepted(car_id):
            continue
        cid = int(car_id)
        if cid not in cars:
            violations.append(f"order {order_id}: unknown car {cid}")
            continue
        order = orders[order_id]
        car = cars[cid]
        if not can_serve_level(car.level, order.level):
            violations.append(f"order {order_id}: car {cid} level {car.level} cannot serve level {order.level}")
        by_car[cid].append(order)

    moving_time = 0
    for cid, car_orders in by_car.items():
        car_orders.sort(key=lambda order: (order.pickup_minute, order.id))
        station = cars[cid].station
        ready = 0
        for order in car_orders:
            move = inst.move_time[(station, order.pickup_station)]
            starts_now = ready == 0 and move == 0 and order.pickup_minute == 0
            if not starts_now and ready + move > latest_arrival_for_pickup(order):
                violations.append(
                    f"car {cid} -> order {order.id}: ready {ready} + move {move} > latest {latest_arrival_for_pickup(order)}"
                )
            moving_time += move
            station = order.return_station
            ready = order_ready_minute(order)
    if moving_time > inst.moving_budget:
        violations.append(f"moving budget exceeded: {moving_time} > {inst.moving_budget}")
    return not violations, moving_time, violations


def _run_ip_one(instance_path_s: str, time_limit: int | None, threads: int | None) -> tuple[dict[str, object], dict[str, object]]:
    from ip_solver import solve_instance, write_plan

    instance_path = Path(instance_path_s)
    scenario_dir = instance_path.parent
    plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    try:
        solution = solve_instance(instance_path, time_limit=time_limit, verbose=False, threads=threads)
        write_plan(solution, plan_path)
        seconds = time.perf_counter() - start
        moving_time = sum(int(row[5]) for row in solution["relocations"])
        accepted_orders = sum(1 for car_id in solution["assignment"] if _is_accepted(car_id))
        runtime_row = {
            "instance": instance_path.name,
            "plan": str(plan_path),
            "status": "ok",
            "seconds": f"{seconds:.3f}",
            "accepted_sales": solution["objective"],
            "profit": solution["profit"],
            "moving_time": moving_time,
            "accepted_orders": accepted_orders,
            "error": "",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        benchmark_row = {
            "instance": instance_path.name,
            "algorithm": "ip_solver",
            "moving_time": moving_time,
            "profit": solution["profit"],
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": accepted_orders,
            "accepted_sales": solution["objective"],
            "status": "ok",
            "error": "",
            "timestamp": runtime_row["timestamp"],
        }
        return runtime_row, benchmark_row
    except Exception as exc:
        seconds = time.perf_counter() - start
        runtime_row = {
            "instance": instance_path.name,
            "plan": str(plan_path),
            "status": "error",
            "seconds": f"{seconds:.3f}",
            "accepted_sales": "",
            "profit": "",
            "moving_time": "",
            "accepted_orders": "",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        benchmark_row = {
            "instance": instance_path.name,
            "algorithm": "ip_solver",
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "accepted_sales": "",
            "status": "error",
            "error": runtime_row["error"],
            "timestamp": runtime_row["timestamp"],
        }
        return runtime_row, benchmark_row


def _run_pipeline_algorithm(instance_path_s: str, algorithm: str, union_seconds: float) -> dict[str, object]:
    instance_path = Path(instance_path_s)
    inst = parse_instance(instance_path)
    start = time.perf_counter()
    try:
        if algorithm == "algo_naive":
            func = getattr(importlib.import_module("algo_naive"), "heuristic_algorithm")
            assignment, _relocation = func(str(instance_path), raw_test=True)
        elif algorithm == "algo_union":
            func = getattr(importlib.import_module("algo_union"), "heuristic_algorithm")
            assignment, _relocation = func(
                str(instance_path),
                max_seconds=union_seconds,
                per_ip_seconds=min(2.0, union_seconds),
                raw_test=True,
            )
        else:
            raise ValueError(f"unsupported pipeline algorithm: {algorithm}")
        seconds = time.perf_counter() - start
        feasible, moving_time, violations = _validate_assignment(inst, assignment)
        return {
            "instance": instance_path.name,
            "algorithm": algorithm,
            "moving_time": moving_time,
            "profit": _profit(inst, assignment),
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": sum(1 for car_id in assignment if _is_accepted(car_id)),
            "accepted_sales": _accepted_sales(inst, assignment),
            "status": "ok" if feasible else "infeasible",
            "error": "" if feasible else "; ".join(violations[:5]),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "algorithm": algorithm,
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "accepted_sales": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def _pipeline_worker(args: tuple[str, bool, tuple[str, ...], int | None, int | None, float]) -> tuple[str, dict[str, object] | None, dict[str, object] | None, list[dict[str, object]]]:
    instance_path_s, needs_ip, algorithms, ip_time_limit, ip_threads, union_seconds = args
    runtime_row = None
    ip_benchmark_row = None
    if needs_ip:
        runtime_row, ip_benchmark_row = _run_ip_one(instance_path_s, ip_time_limit, ip_threads)
    algorithm_rows = [_run_pipeline_algorithm(instance_path_s, algorithm, union_seconds) for algorithm in algorithms]
    return instance_path_s, runtime_row, ip_benchmark_row, algorithm_rows


def _instance_paths(root: Path, scenarios: Iterable[str] | None = None) -> list[Path]:
    if root.is_dir() and any(root.glob("*.txt")):
        return sorted(root.glob("*.txt"))
    selected = set(scenarios or [])
    scenario_dirs = [
        path for path in sorted(root.iterdir())
        if path.is_dir() and path.name.startswith("S") and (not selected or path.name in selected)
    ]
    paths: list[Path] = []
    for scenario_dir in scenario_dirs:
        paths.extend(sorted(scenario_dir.glob("*.txt")))
    return paths


def benchmark_pipeline(
    root: str | Path,
    scenarios: Iterable[str] | None = None,
    jobs: int = 1,
    union_seconds: float = 10.0,
    ip_time_limit: int | None = None,
    ip_threads: int | None = 1,
    force_ip: bool = False,
    force_algorithms: bool = False,
    skip_ip: bool = False,
    skip_algorithms: bool = False,
) -> None:
    root_path = Path(root)
    paths = _instance_paths(root_path, scenarios)
    if not paths:
        raise FileNotFoundError(f"no .txt instances found under {root_path}")

    tasks: list[tuple[str, bool, tuple[str, ...], int | None, int | None, float]] = []
    for instance_path in paths:
        scenario_dir = instance_path.parent
        plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
        ip_done = plan_path.exists() and _existing_ok(scenario_dir / "run_time.csv", ("instance",), (instance_path.name,))
        needs_ip = (not skip_ip) and (force_ip or not ip_done)
        algorithms = tuple(
            algorithm
            for algorithm in PIPELINE_ALGORITHMS
            if not skip_algorithms
            and (
                force_algorithms
                or not _existing_ok(
                    scenario_dir / "benchmark_results.csv",
                    ("instance", "algorithm"),
                    (instance_path.name, algorithm),
                )
            )
        )
        ip_benchmark_done = _existing_ok(scenario_dir / "benchmark_results.csv", ("instance", "algorithm"), (instance_path.name, "ip_solver"))
        if not skip_ip and not needs_ip and not ip_benchmark_done:
            needs_ip = True
        if needs_ip or algorithms:
            tasks.append((str(instance_path), needs_ip, algorithms, ip_time_limit, ip_threads, union_seconds))

    print(
        f"benchmark pipeline: instances={len(paths)} jobs={len(tasks)} workers={jobs} "
        f"union_seconds={union_seconds} ip_threads={ip_threads or 'gurobi-default'}",
        flush=True,
    )
    if not tasks:
        return

    with _make_executor(max(1, jobs)) as pool:
        future_to_task = {pool.submit(_pipeline_worker, task): task for task in tasks}
        for idx, future in enumerate(as_completed(future_to_task), start=1):
            instance_path_s, runtime_row, ip_benchmark_row, algorithm_rows = future.result()
            instance_path = Path(instance_path_s)
            scenario_dir = instance_path.parent
            if runtime_row is not None:
                _upsert(scenario_dir / "run_time.csv", runtime_row, IP_FIELDS, ("instance",))
            if ip_benchmark_row is not None:
                _upsert(scenario_dir / "benchmark_results.csv", ip_benchmark_row, RESULT_FIELDS, ("instance", "algorithm"))
            for row in algorithm_rows:
                _upsert(scenario_dir / "benchmark_results.csv", row, RESULT_FIELDS, ("instance", "algorithm"))
            status = []
            if runtime_row is not None:
                status.append(f"ip={runtime_row['status']}:{runtime_row['seconds']}s")
            status.extend(f"{row['algorithm']}={row['status']}:{row['execution_time']}s" for row in algorithm_rows)
            print(f"[{idx}/{len(tasks)}] {scenario_dir.name}/{instance_path.name} {' '.join(status)}", flush=True)


def _default_output_path(directory_path: Path, output_dir: str | Path | None) -> Path | None:
    if output_dir is None:
        return None
    output_root = Path(output_dir)
    return output_root / f"{directory_path.name}_benchmark_results.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark solver .py files on local instance directories.")
    parser.add_argument(
        "directory_path",
        nargs="?",
        default="data/exp_instances/S1",
        help="directory containing .txt instances, e.g. data/exp_instances/S1",
    )
    parser.add_argument(
        "python_files",
        nargs="*",
        default=["algo1.py", "algo5.py"],
        help="solver .py files to benchmark, e.g. algo1.py algo5.py",
    )
    parser.add_argument("--output-csv", help="CSV path for one directory; defaults to <directory>/benchmark_results.csv")
    parser.add_argument(
        "--all-subdirs",
        action="store_true",
        help="treat directory_path as a parent and benchmark each immediate subdirectory containing .txt files",
    )
    parser.add_argument(
        "--output-dir",
        help="when using --all-subdirs, write one CSV per subdirectory into this directory",
    )
    parser.add_argument(
        "--raw-test",
        action="store_true",
        help="skip IP solvers by passing raw_test=True",
    )
    parser.add_argument(
        "--parallel-pipeline",
        action="store_true",
        help="parallel mode: run each instance as ip_solver -> algo_naive -> algo_union",
    )
    parser.add_argument("--root", default=None, help="root for --parallel-pipeline; defaults to directory_path")
    parser.add_argument("--scenario", action="append", help="scenario folder to include in --parallel-pipeline; repeatable")
    parser.add_argument("--jobs", type=int, default=1, help="parallel instance workers for --parallel-pipeline")
    parser.add_argument("--union-seconds", type=float, default=10.0, help="time budget for algo_union")
    parser.add_argument("--ip-time-limit", type=int, default=None, help="optional Gurobi time limit per IP instance")
    parser.add_argument("--ip-threads", type=int, default=1, help="Gurobi threads per IP job; use 0 for default")
    parser.add_argument("--force-ip", action="store_true", help="rerun IP even if run_time.csv and plan exist")
    parser.add_argument("--force-algorithms", action="store_true", help="rerun algo_naive and algo_union")
    parser.add_argument("--skip-ip", action="store_true", help="skip IP stage in --parallel-pipeline")
    parser.add_argument("--skip-algorithms", action="store_true", help="skip algo_naive/algo_union stage in --parallel-pipeline")
    args = parser.parse_args()

    if args.parallel_pipeline:
        benchmark_pipeline(
            root=args.root or args.directory_path,
            scenarios=args.scenario,
            jobs=args.jobs,
            union_seconds=args.union_seconds,
            ip_time_limit=args.ip_time_limit,
            ip_threads=args.ip_threads if args.ip_threads > 0 else None,
            force_ip=args.force_ip,
            force_algorithms=args.force_algorithms,
            skip_ip=args.skip_ip,
            skip_algorithms=args.skip_algorithms,
        )
        return

    root = Path(args.directory_path)
    if args.all_subdirs:
        dirs = [path for path in sorted(root.iterdir()) if path.is_dir() and any(path.glob("*.txt"))]
        if not dirs:
            raise FileNotFoundError(f"no subdirectories with .txt instances found in {root}")
        for directory in dirs:
            csv_path = benchmark_local(
                directory,
                args.python_files,
                output_csv=_default_output_path(directory, args.output_dir),
                raw_test=args.raw_test,
            )
            print(f"wrote {csv_path}")
    else:
        csv_path = benchmark_local(root, args.python_files, output_csv=args.output_csv, raw_test=args.raw_test)
        print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
