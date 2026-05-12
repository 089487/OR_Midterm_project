from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import signal
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Iterable

from mtp_common import Instance, can_serve_level, latest_arrival_for_pickup, order_ready_minute, parse_instance


STOP_REQUESTED = False
IP_MOVING_RE = re.compile(r"^Moving time used:\s*([0-9]+)")


def _request_stop(signum, frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"\nreceived signal {signum}; stopping after the current benchmark...", flush=True)


def _is_accepted(car_id: object) -> bool:
    return car_id is not None and int(car_id) > 0


def _profit(inst: Instance, assignment: Iterable[object]) -> int:
    accepted_revenue = sum(
        order.revenue
        for order, car_id in zip(inst.orders, assignment)
        if _is_accepted(car_id)
    )
    total_revenue = sum(order.revenue for order in inst.orders)
    return accepted_revenue - 2 * (total_revenue - accepted_revenue)


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
            starts_at_horizon_same_station = ready == 0 and move == 0 and order.pickup_minute == 0
            if not starts_at_horizon_same_station and ready + move > latest_arrival_for_pickup(order):
                violations.append(
                    f"car {cid} -> order {order.id}: ready {ready} + move {move} "
                    f"> latest {latest_arrival_for_pickup(order)}"
                )
            moving_time += move
            station = order.return_station
            ready = order_ready_minute(order)

    if moving_time > inst.moving_budget:
        violations.append(f"moving budget exceeded: {moving_time} > {inst.moving_budget}")
    return not violations, moving_time, violations


def _load_solver(python_file: Path) -> tuple[str, ModuleType]:
    solver_path = python_file.resolve()
    module_name = f"_benchmark_solver_{solver_path.stem}_{abs(hash(solver_path))}"
    spec = importlib.util.spec_from_file_location(module_name, solver_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import solver from {solver_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "heuristic_algorithm"):
        raise AttributeError(f"{solver_path} does not define heuristic_algorithm(instance_path)")
    return solver_path.stem, module


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "instance",
        "algorithm",
        "moving_time",
        "profit",
        "execution_time",
        "accepted_orders",
        "status",
        "error",
        "timestamp",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{name: row.get(name, "") for name in fieldnames} for row in rows])


def _upsert_row(csv_path: Path, row: dict[str, object]) -> None:
    rows = _read_rows(csv_path)
    key = (str(row["instance"]), str(row["algorithm"]))
    by_key = {(r.get("instance", ""), r.get("algorithm", "")): r for r in rows}
    by_key[key] = row
    ordered = sorted(by_key.values(), key=lambda r: (str(r.get("instance", "")), str(r.get("algorithm", ""))))
    _write_rows(csv_path, ordered)


def _ip_runtime_by_instance(scenario_dir: Path) -> dict[str, dict[str, str]]:
    rows = _read_rows(scenario_dir / "run_time.csv")
    return {Path(row.get("instance", "")).name: row for row in rows}


def _ip_moving_time(plan_path: Path) -> int | str:
    if not plan_path.exists():
        return ""
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        match = IP_MOVING_RE.match(line)
        if match:
            return int(match.group(1))
    return ""


def _ip_accepted_orders(plan_path: Path) -> int | str:
    if not plan_path.exists():
        return ""
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Accepted orders:"):
            return int(line.split(":", 1)[1].split("/", 1)[0].strip())
    return ""


def _ip_row(instance_path: Path, scenario_dir: Path, runtime_rows: dict[str, dict[str, str]]) -> dict[str, object]:
    plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
    runtime = runtime_rows.get(instance_path.name, {})
    status = "ok" if plan_path.exists() else "missing_plan"
    return {
        "instance": instance_path.name,
        "algorithm": "ip_solver",
        "moving_time": _ip_moving_time(plan_path),
        "profit": runtime.get("profit", ""),
        "execution_time": runtime.get("seconds", ""),
        "accepted_orders": _ip_accepted_orders(plan_path),
        "status": status,
        "error": "" if status == "ok" else f"missing {plan_path}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _solver_row(instance_path: Path, solver_name: str, module: ModuleType) -> dict[str, object]:
    inst = parse_instance(instance_path)
    start = time.perf_counter()
    try:
        assignment, relocation = module.heuristic_algorithm(str(instance_path))
        seconds = time.perf_counter() - start
        feasible, route_moving_time, violations = _validate_assignment(inst, assignment)
        return {
            "instance": instance_path.name,
            "algorithm": solver_name,
            "moving_time": route_moving_time,
            "profit": _profit(inst, assignment),
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": sum(1 for car_id in assignment if _is_accepted(car_id)),
            "status": "ok" if feasible else "infeasible",
            "error": "" if feasible else "; ".join(violations[:5]),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "algorithm": solver_name,
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def run_benchmarks(root: Path, solver_paths: list[Path], force: bool = False) -> None:
    solvers = [_load_solver(path) for path in solver_paths]
    scenario_dirs = sorted(path for path in root.iterdir() if path.is_dir() and list(path.glob("*.txt")))
    total_instances = sum(len(list(path.glob("*.txt"))) for path in scenario_dirs)
    total_jobs = total_instances * (len(solvers) + 1)
    completed = 0
    print(f"found {total_instances} instances; total rows including ip_solver = {total_jobs}", flush=True)

    for scenario_dir in scenario_dirs:
        csv_path = scenario_dir / "benchmark_results.csv"
        existing = {
            (row.get("instance", ""), row.get("algorithm", "")): row
            for row in _read_rows(csv_path)
            if row.get("status") == "ok"
        }
        runtime_rows = _ip_runtime_by_instance(scenario_dir)

        for instance_path in sorted(scenario_dir.glob("*.txt")):
            if STOP_REQUESTED:
                print("stop requested; exiting before starting next benchmark.", flush=True)
                return

            for row in [_ip_row(instance_path, scenario_dir, runtime_rows)]:
                key = (str(row["instance"]), str(row["algorithm"]))
                if key in existing and not force:
                    completed += 1
                    print(f"[{completed}/{total_jobs}] skip {scenario_dir.name}/{instance_path.name} ip_solver", flush=True)
                    continue
                _upsert_row(csv_path, row)
                completed += 1
                print(f"[{completed}/{total_jobs}] wrote {scenario_dir.name}/{instance_path.name} ip_solver", flush=True)

            for solver_name, module in solvers:
                key = (instance_path.name, solver_name)
                if key in existing and not force:
                    completed += 1
                    print(f"[{completed}/{total_jobs}] skip {scenario_dir.name}/{instance_path.name} {solver_name}", flush=True)
                    continue
                print(f"[{completed + 1}/{total_jobs}] running {scenario_dir.name}/{instance_path.name} {solver_name}", flush=True)
                row = _solver_row(instance_path, solver_name, module)
                _upsert_row(csv_path, row)
                completed += 1
                print(
                    f"[{completed}/{total_jobs}] {row['status']} {scenario_dir.name}/{instance_path.name} "
                    f"{solver_name} seconds={row['execution_time']} profit={row['profit']} "
                    f"moving_time={row['moving_time']}",
                    flush=True,
                )

    print("benchmark runner finished.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark algo solvers and collect ip_solver plan metrics.")
    parser.add_argument("--root", default="data/exp_instances")
    parser.add_argument("--solver", action="append", default=None, help="solver .py path; can be repeated")
    parser.add_argument("--force", action="store_true", help="rerun rows even if benchmark_results.csv has ok rows")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    solver_paths = [Path(path) for path in (args.solver or ["algo1.py", "algo5.py"])]
    run_benchmarks(Path(args.root), solver_paths, force=args.force)


if __name__ == "__main__":
    main()
