from __future__ import annotations

import argparse
import csv
import importlib
import multiprocessing as mp
import time
from pathlib import Path
from typing import Iterable

from mtp_common import Instance, can_serve_level, latest_arrival_for_pickup, order_ready_minute, parse_instance

ALGO_SPECS = {
    "algo2": ("heuristic_algo2", "heuristic_algorithm2"),
    "algo3": ("heuristic_algo3", "heuristic_algorithm3"),
    "algo4": ("heuristic_algo4", "heuristic_algorithm4"),
}
FIELDS = [
    "instance", "algorithm", "moving_time", "profit", "execution_time",
    "accepted_orders", "status", "error", "timestamp",
]


def is_accepted(car_id: object) -> bool:
    return car_id is not None and int(car_id) > 0


def profit(inst: Instance, assignment: Iterable[object]) -> int:
    accepted = sum(o.revenue for o, c in zip(inst.orders, assignment) if is_accepted(c))
    total = sum(o.revenue for o in inst.orders)
    return accepted - 2 * (total - accepted)


def validate(inst: Instance, assignment: Iterable[object]) -> tuple[bool, int, list[str]]:
    cars = {c.id: c for c in inst.cars}
    orders = {o.id: o for o in inst.orders}
    by_car = {c.id: [] for c in inst.cars}
    violations = []
    for oid, cid_obj in enumerate(assignment, start=1):
        if not is_accepted(cid_obj):
            continue
        cid = int(cid_obj)
        if cid not in cars:
            violations.append(f"order {oid}: unknown car {cid}")
            continue
        car = cars[cid]
        order = orders[oid]
        if not can_serve_level(car.level, order.level):
            violations.append(f"order {oid}: car {cid} level {car.level} cannot serve level {order.level}")
        by_car[cid].append(order)

    moving = 0
    for cid, car_orders in by_car.items():
        car_orders.sort(key=lambda o: (o.pickup_minute, o.id))
        station = cars[cid].station
        ready = 0
        for order in car_orders:
            move = inst.move_time[(station, order.pickup_station)]
            starts_at_horizon_same_station = ready == 0 and move == 0 and order.pickup_minute == 0
            if not starts_at_horizon_same_station and ready + move > latest_arrival_for_pickup(order):
                violations.append(
                    f"car {cid} -> order {order.id}: ready {ready} + move {move} > latest {latest_arrival_for_pickup(order)}"
                )
            moving += move
            station = order.return_station
            ready = order_ready_minute(order)
    if moving > inst.moving_budget:
        violations.append(f"moving budget exceeded: {moving} > {inst.moving_budget}")
    return not violations, moving, violations


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in FIELDS} for row in rows])


def upsert(path: Path, row: dict[str, object]) -> None:
    rows = read_rows(path)
    by_key = {(r.get("instance", ""), r.get("algorithm", "")): r for r in rows}
    by_key[(str(row["instance"]), str(row["algorithm"]))] = row
    ordered = sorted(by_key.values(), key=lambda r: (str(r.get("instance", "")), str(r.get("algorithm", ""))))
    write_rows(path, ordered)


def run_one(instance_path: Path, algo_name: str, max_seconds: float) -> dict[str, object]:
    inst = parse_instance(instance_path)
    module_name, function_name = ALGO_SPECS[algo_name]
    func = getattr(importlib.import_module(module_name), function_name)
    start = time.perf_counter()
    try:
        kwargs = {"max_seconds": max_seconds, "raw_test": True}
        if algo_name == "algo4":
            kwargs["per_ip_seconds"] = min(2.0, max_seconds)
        assignment, _relocation = func(str(instance_path), **kwargs)
        seconds = time.perf_counter() - start
        feasible, moving, violations = validate(inst, assignment)
        return {
            "instance": instance_path.name,
            "algorithm": algo_name,
            "moving_time": moving,
            "profit": profit(inst, assignment),
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": sum(1 for c in assignment if is_accepted(c)),
            "status": "ok" if feasible else "infeasible",
            "error": "" if feasible else "; ".join(violations[:5]),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "algorithm": algo_name,
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def scenario_sort_key(path: Path) -> tuple[int, str]:
    suffix = path.name[1:] if path.name.startswith("S") else ""
    return (int(suffix) if suffix.isdigit() else 9999, path.name)


def run_scenario(args: tuple[str, list[str], float, bool]) -> str:
    scenario_dir_s, algo_names, max_seconds, force = args
    scenario_dir = Path(scenario_dir_s)
    csv_path = scenario_dir / "benchmark_results.csv"
    existing = {
        (r.get("instance", ""), r.get("algorithm", ""))
        for r in read_rows(csv_path)
        if r.get("status") == "ok"
    }
    log_path = scenario_dir / "algo234_run.log"
    jobs = [(p, a) for p in sorted(scenario_dir.glob("*.txt")) for a in algo_names]
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"START {time.strftime('%Y-%m-%d %H:%M:%S')} jobs={len(jobs)} max_seconds={max_seconds}\n")
        log.flush()
        for idx, (instance_path, algo_name) in enumerate(jobs, start=1):
            if not force and (instance_path.name, algo_name) in existing:
                msg = f"[{idx}/{len(jobs)}] skip {instance_path.name} {algo_name}"
                print(f"{scenario_dir.name} {msg}", flush=True)
                log.write(msg + "\n")
                log.flush()
                continue
            msg = f"[{idx}/{len(jobs)}] running {instance_path.name} {algo_name}"
            print(f"{scenario_dir.name} {msg}", flush=True)
            log.write(msg + "\n")
            log.flush()
            row = run_one(instance_path, algo_name, max_seconds)
            upsert(csv_path, row)
            msg = (
                f"[{idx}/{len(jobs)}] {row['status']} {instance_path.name} {algo_name} "
                f"seconds={row['execution_time']} profit={row['profit']} moving_time={row['moving_time']}"
            )
            print(f"{scenario_dir.name} {msg}", flush=True)
            log.write(msg + "\n")
            log.flush()
        log.write(f"DONE {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return scenario_dir.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/exp_instances")
    parser.add_argument("--max-seconds", type=float, default=10.0)
    parser.add_argument("--jobs", type=int, default=14)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--algorithm", action="append", choices=sorted(ALGO_SPECS), default=None)
    args = parser.parse_args()
    algo_names = args.algorithm or ["algo2", "algo3", "algo4"]
    scenario_dirs = sorted([p for p in Path(args.root).iterdir() if p.is_dir() and p.name.startswith("S")], key=scenario_sort_key)
    tasks = [(str(p), algo_names, args.max_seconds, args.force) for p in scenario_dirs]
    print(
        f"parallel scenario jobs={len(tasks)} workers={args.jobs} "
        f"algorithms={','.join(algo_names)} max_seconds={args.max_seconds}",
        flush=True,
    )
    with mp.Pool(processes=min(args.jobs, len(tasks))) as pool:
        for name in pool.imap_unordered(run_scenario, tasks):
            print(f"scenario done: {name}", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
