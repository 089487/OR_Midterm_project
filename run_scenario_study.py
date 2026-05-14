from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable

from algo_naive import heuristic_algorithm as naive_algorithm
from algo_union import heuristic_algorithm as union_algorithm
from data.generate_code import CONFIGS, IEDOProjectGenerator
from mtp_common import Instance, can_serve_level, latest_arrival_for_pickup, order_ready_minute, parse_instance


DEFAULT_SCENARIOS = ("S6", "S8", "S10", "S13", "S14")
ALGORITHMS = ("algo_naive", "algo_union")
RESULT_FIELDS = [
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
IP_FIELDS = ["instance", "plan", "status", "seconds", "accepted_sales", "profit", "error", "timestamp"]


def _scenario_sort_key(name: str) -> tuple[int, str]:
    return (int(name[1:]), name) if name.startswith("S") and name[1:].isdigit() else (9999, name)


def _generate_one(args: tuple[str, int, int, str]) -> str:
    scenario, index, seed, out_dir_s = args
    if scenario not in CONFIGS:
        raise ValueError(f"unknown scenario {scenario}; choices: {', '.join(sorted(CONFIGS, key=_scenario_sort_key))}")
    random.seed(seed)
    out_dir = Path(out_dir_s)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{scenario}_study_{index:03d}.txt"
    path.write_text(IEDOProjectGenerator().create_instance(CONFIGS[scenario]), encoding="utf-8")
    return str(path)


def generate_instances(
    root: Path,
    scenarios: Iterable[str],
    instances: int,
    seed: int,
    workers: int,
    force: bool,
) -> None:
    jobs: list[tuple[str, int, int, str]] = []
    for scenario in scenarios:
        scenario_dir = root / scenario
        if force:
            for old in scenario_dir.glob(f"{scenario}_study_*.txt"):
                old.unlink()
        for index in range(1, instances + 1):
            path = scenario_dir / f"{scenario}_study_{index:03d}.txt"
            if path.exists() and not force:
                continue
            jobs.append((scenario, index, seed + 100000 * _scenario_sort_key(scenario)[0] + index, str(scenario_dir)))

    if not jobs:
        print("generation: all requested instances already exist", flush=True)
        return
    print(f"generation: creating {len(jobs)} instances with workers={workers}", flush=True)
    with _make_executor(max(1, workers)) as pool:
        for completed, future in enumerate(as_completed([pool.submit(_generate_one, job) for job in jobs]), start=1):
            path = future.result()
            if completed == 1 or completed % 25 == 0 or completed == len(jobs):
                print(f"generation [{completed}/{len(jobs)}] {path}", flush=True)


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
    key = tuple(str(row[field]) for field in key_fields)
    by_key = {tuple(str(existing.get(field, "")) for field in key_fields): existing for existing in rows}
    by_key[key] = row
    ordered = sorted(by_key.values(), key=lambda item: tuple(str(item.get(field, "")) for field in key_fields))
    _write_rows(path, ordered, fieldnames)


def _instance_paths(root: Path, scenarios: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for scenario in sorted(scenarios, key=_scenario_sort_key):
        paths.extend(sorted((root / scenario).glob("*.txt")))
    return paths


def _run_ip_one(instance_path: Path, time_limit: int | None, threads: int | None) -> dict[str, object]:
    from ip_solver import solve_instance, write_plan

    scenario_dir = instance_path.parent
    plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    try:
        solution = solve_instance(instance_path, time_limit=time_limit, verbose=False, threads=threads)
        write_plan(solution, plan_path)
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "plan": str(plan_path),
            "status": "ok",
            "seconds": f"{seconds:.3f}",
            "accepted_sales": solution["objective"],
            "profit": solution["profit"],
            "error": "",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        seconds = time.perf_counter() - start
        return {
            "instance": instance_path.name,
            "plan": str(plan_path),
            "status": "error",
            "seconds": f"{seconds:.3f}",
            "accepted_sales": "",
            "profit": "",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def run_ip(root: Path, scenarios: Iterable[str], force: bool, time_limit: int | None, threads: int | None) -> None:
    paths = _instance_paths(root, scenarios)
    print(f"ip_solver: {len(paths)} instances", flush=True)
    for idx, instance_path in enumerate(paths, start=1):
        scenario_dir = instance_path.parent
        plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
        run_time_path = scenario_dir / "run_time.csv"
        existing = {
            Path(row.get("instance", "")).name: row
            for row in _read_rows(run_time_path)
            if row.get("status") == "ok"
        }
        if plan_path.exists() and instance_path.name in existing and not force:
            if idx == 1 or idx % 25 == 0 or idx == len(paths):
                print(f"ip_solver [{idx}/{len(paths)}] skip {instance_path}", flush=True)
            continue

        row = _run_ip_one(instance_path, time_limit, threads)
        _upsert(run_time_path, row, IP_FIELDS, ("instance",))
        print(
            f"ip_solver [{idx}/{len(paths)}] {row['status']} {instance_path.name} "
            f"seconds={row['seconds']} profit={row['profit']}",
            flush=True,
        )


def _is_accepted(car_id: object) -> bool:
    try:
        return int(car_id) > 0
    except (TypeError, ValueError):
        return False


def _profit(inst: Instance, assignment: Iterable[object]) -> int:
    accepted_revenue = sum(order.revenue for order, car_id in zip(inst.orders, assignment) if _is_accepted(car_id))
    total_revenue = sum(order.revenue for order in inst.orders)
    return accepted_revenue - 2 * (total_revenue - accepted_revenue)


def _total_revenue(inst: Instance) -> int:
    return sum(order.revenue for order in inst.orders)


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


def _run_algorithm_one(args: tuple[str, str, float]) -> dict[str, object]:
    instance_path = Path(args[0])
    algorithm = args[1]
    union_seconds = args[2]
    inst = parse_instance(instance_path)
    start = time.perf_counter()
    try:
        if algorithm == "algo_naive":
            assignment, _ = naive_algorithm(instance_path, raw_test=True)
        elif algorithm == "algo_union":
            assignment, _ = union_algorithm(
                instance_path,
                max_seconds=union_seconds,
                per_ip_seconds=min(2.0, union_seconds),
                raw_test=True,
            )
        else:
            raise ValueError(f"unknown algorithm {algorithm}")
        seconds = time.perf_counter() - start
        feasible, moving_time, violations = _validate_assignment(inst, assignment)
        return {
            "instance": instance_path.name,
            "algorithm": algorithm,
            "moving_time": moving_time,
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
            "algorithm": algorithm,
            "moving_time": "",
            "profit": "",
            "execution_time": f"{seconds:.6f}",
            "accepted_orders": "",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def run_algorithms(
    root: Path,
    scenarios: Iterable[str],
    workers: int,
    force: bool,
    union_seconds: float,
) -> None:
    jobs: list[tuple[str, str, float]] = []
    for instance_path in _instance_paths(root, scenarios):
        csv_path = instance_path.parent / "benchmark_results.csv"
        existing = {
            (row.get("instance", ""), row.get("algorithm", ""))
            for row in _read_rows(csv_path)
            if row.get("status") == "ok"
        }
        for algorithm in ALGORITHMS:
            if not force and (instance_path.name, algorithm) in existing:
                continue
            jobs.append((str(instance_path), algorithm, union_seconds))

    print(f"algorithms: {len(jobs)} jobs with workers={workers}", flush=True)
    if not jobs:
        return
    with _make_executor(max(1, workers)) as pool:
        future_to_job = {pool.submit(_run_algorithm_one, job): job for job in jobs}
        for idx, future in enumerate(as_completed(future_to_job), start=1):
            instance_path_s, algorithm, _ = future_to_job[future]
            instance_path = Path(instance_path_s)
            row = future.result()
            _upsert(instance_path.parent / "benchmark_results.csv", row, RESULT_FIELDS, ("instance", "algorithm"))
            print(
                f"algorithms [{idx}/{len(jobs)}] {row['status']} {instance_path.parent.name}/{row['instance']} "
                f"{algorithm} seconds={row['execution_time']} profit={row['profit']}",
                flush=True,
            )


def _existing_ok(path: Path, key_fields: tuple[str, ...], key: tuple[str, ...]) -> bool:
    for row in _read_rows(path):
        if tuple(row.get(field, "") for field in key_fields) == key and row.get("status") == "ok":
            return True
    return False


def _pipeline_job(
    instance_path: Path,
    force_ip: bool,
    force_algorithms: bool,
    run_ip_stage: bool,
    run_algorithm_stage: bool,
) -> tuple[str, bool, tuple[str, ...]]:
    scenario_dir = instance_path.parent
    plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
    ip_done = plan_path.exists() and _existing_ok(scenario_dir / "run_time.csv", ("instance",), (instance_path.name,))
    missing_algorithms = ()
    if run_algorithm_stage:
        missing_algorithms = tuple(
            algorithm
            for algorithm in ALGORITHMS
            if force_algorithms
            or not _existing_ok(
                scenario_dir / "benchmark_results.csv",
                ("instance", "algorithm"),
                (instance_path.name, algorithm),
            )
        )
    return str(instance_path), run_ip_stage and (force_ip or not ip_done), missing_algorithms


def _run_instance_pipeline(
    args: tuple[str, bool, tuple[str, ...], int | None, int | None, float],
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    instance_path = Path(args[0])
    needs_ip = args[1]
    algorithms = args[2]
    ip_time_limit = args[3]
    ip_threads = args[4]
    union_seconds = args[5]

    ip_row = _run_ip_one(instance_path, ip_time_limit, ip_threads) if needs_ip else None
    algorithm_rows = [_run_algorithm_one((str(instance_path), algorithm, union_seconds)) for algorithm in algorithms]
    return ip_row, algorithm_rows


def run_instance_pipelines(
    root: Path,
    scenarios: Iterable[str],
    workers: int,
    force_ip: bool,
    force_algorithms: bool,
    ip_time_limit: int | None,
    ip_threads: int | None,
    union_seconds: float,
    run_ip_stage: bool = True,
    run_algorithm_stage: bool = True,
) -> None:
    jobs: list[tuple[str, bool, tuple[str, ...], int | None, int | None, float]] = []
    for instance_path in _instance_paths(root, scenarios):
        path, needs_ip, algorithms = _pipeline_job(
            instance_path,
            force_ip,
            force_algorithms,
            run_ip_stage,
            run_algorithm_stage,
        )
        if needs_ip or algorithms:
            jobs.append((path, needs_ip, algorithms, ip_time_limit, ip_threads, union_seconds))

    print(
        f"instance pipeline: {len(jobs)} jobs with workers={workers}, "
        f"ip_threads={ip_threads or 'gurobi-default'}, union_seconds={union_seconds}",
        flush=True,
    )
    if not jobs:
        return
    with _make_executor(max(1, workers)) as pool:
        future_to_job = {pool.submit(_run_instance_pipeline, job): job for job in jobs}
        for idx, future in enumerate(as_completed(future_to_job), start=1):
            instance_path = Path(future_to_job[future][0])
            ip_row, algorithm_rows = future.result()
            if ip_row is not None:
                _upsert(instance_path.parent / "run_time.csv", ip_row, IP_FIELDS, ("instance",))
            for row in algorithm_rows:
                _upsert(instance_path.parent / "benchmark_results.csv", row, RESULT_FIELDS, ("instance", "algorithm"))
            status_bits = []
            if ip_row is not None:
                status_bits.append(f"ip={ip_row['status']}:{ip_row['seconds']}s")
            status_bits.extend(
                f"{row['algorithm']}={row['status']}:{row['execution_time']}s" for row in algorithm_rows
            )
            print(
                f"pipeline [{idx}/{len(jobs)}] {instance_path.parent.name}/{instance_path.name} "
                + " ".join(status_bits),
                flush=True,
            )


def _make_executor(workers: int):
    try:
        return ProcessPoolExecutor(max_workers=workers)
    except PermissionError:
        print("process pool unavailable in this environment; falling back to a single local thread", flush=True)
        return ThreadPoolExecutor(max_workers=1)


def add_ip_rows(root: Path, scenarios: Iterable[str]) -> None:
    for scenario in scenarios:
        scenario_dir = root / scenario
        runtime = {
            row.get("instance", ""): row
            for row in _read_rows(scenario_dir / "run_time.csv")
            if row.get("status") == "ok"
        }
        for instance_path in sorted(scenario_dir.glob("*.txt")):
            plan_path = scenario_dir / "plan" / f"{instance_path.stem}_optimal_plan.txt"
            row = runtime.get(instance_path.name, {})
            benchmark_row = {
                "instance": instance_path.name,
                "algorithm": "ip_solver",
                "moving_time": "",
                "profit": row.get("profit", ""),
                "execution_time": row.get("seconds", ""),
                "accepted_orders": "",
                "status": "ok" if row.get("status") == "ok" and plan_path.exists() else "missing_ip",
                "error": "" if row.get("status") == "ok" and plan_path.exists() else "missing IP runtime or plan",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            _upsert(scenario_dir / "benchmark_results.csv", benchmark_row, RESULT_FIELDS, ("instance", "algorithm"))


def summarize_results(root: Path, scenarios: Iterable[str], bins: int) -> None:
    summary_rows: list[dict[str, object]] = []
    combined_gaps: dict[str, dict[str, list[float]]] = {}
    for scenario in sorted(scenarios, key=_scenario_sort_key):
        rows = _read_rows(root / scenario / "benchmark_results.csv")
        by_instance: dict[str, dict[str, dict[str, str]]] = {}
        for row in rows:
            if row.get("status") == "ok":
                by_instance.setdefault(row["instance"], {})[row["algorithm"]] = row

        gap_by_algorithm: dict[str, list[float]] = {algorithm: [] for algorithm in ALGORITHMS}
        profit_by_algorithm: dict[str, list[float]] = {algorithm: [] for algorithm in ALGORITHMS}
        time_by_algorithm: dict[str, list[float]] = {algorithm: [] for algorithm in ALGORITHMS}
        for instance_name, algos in by_instance.items():
            if "ip_solver" not in algos:
                continue
            inst = parse_instance(root / scenario / instance_name)
            total_revenue = _total_revenue(inst)
            ip_profit = float(algos["ip_solver"]["profit"])
            ip_objective = ip_profit + 2 * total_revenue
            if ip_objective <= 0:
                continue
            for algorithm in ALGORITHMS:
                if algorithm not in algos:
                    continue
                profit = float(algos[algorithm]["profit"])
                gap_by_algorithm[algorithm].append((ip_profit - profit) / ip_objective)
                profit_by_algorithm[algorithm].append(profit)
                time_by_algorithm[algorithm].append(float(algos[algorithm]["execution_time"]))

        combined_gaps[scenario] = gap_by_algorithm
        for algorithm in ALGORITHMS:
            gaps = gap_by_algorithm[algorithm]
            if not gaps:
                continue
            summary_rows.append(
                {
                    "scenario": scenario,
                    "algorithm": algorithm,
                    "instances": len(gaps),
                    "gap_mean": round(statistics.mean(gaps), 8),
                    "gap_std": round(statistics.stdev(gaps), 8) if len(gaps) > 1 else 0.0,
                    "gap_min": round(min(gaps), 8),
                    "gap_max": round(max(gaps), 8),
                    "gap_mean_pct": round(100 * statistics.mean(gaps), 6),
                    "gap_std_pct": round(100 * statistics.stdev(gaps), 6) if len(gaps) > 1 else 0.0,
                    "profit_mean": round(statistics.mean(profit_by_algorithm[algorithm]), 6),
                    "execution_time_mean": round(statistics.mean(time_by_algorithm[algorithm]), 6),
                }
            )
        _write_histogram(root / scenario / "optimal_gap_histogram.svg", scenario, gap_by_algorithm, bins)

    _write_rows(
        root / "scenario_gap_summary.csv",
        summary_rows,
        [
            "scenario",
            "algorithm",
            "instances",
            "gap_mean",
            "gap_std",
            "gap_min",
            "gap_max",
            "gap_mean_pct",
            "gap_std_pct",
            "profit_mean",
            "execution_time_mean",
        ],
    )
    _write_combined_histogram(root / "optimal_gap_histograms_combined.svg", combined_gaps, bins)


def _write_histogram(path: Path, scenario: str, gap_by_algorithm: dict[str, list[float]], bins: int) -> None:
    values = [100 * gap for gaps in gap_by_algorithm.values() for gap in gaps]
    if not values:
        return
    lo = min(values)
    hi = max(values)
    if math.isclose(lo, hi):
        lo -= 0.5
        hi += 0.5
    step = (hi - lo) / bins
    counts: dict[str, list[int]] = {}
    for algorithm, gaps in gap_by_algorithm.items():
        bucket = [0] * bins
        for gap in gaps:
            value = 100 * gap
            idx = min(bins - 1, max(0, int((value - lo) / step)))
            bucket[idx] += 1
        counts[algorithm] = bucket

    width = 1100
    height = 520
    left = 70
    right = 30
    top = 65
    chart_h = 340
    chart_w = width - left - right
    max_count = max(max(bucket) for bucket in counts.values()) or 1
    group_w = chart_w / bins
    bar_w = max(1.0, group_w * 0.7 / len(ALGORITHMS))

    def esc(text: object) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:22px;font-weight:700}.label{font-size:12px}.axis{stroke:#374151;stroke-width:1}</style>',
        f'<text x="{left}" y="34" class="title">{esc(scenario)} Accepted-Reward Gap Histogram</text>',
        f'<line x1="{left}" y1="{top + chart_h}" x2="{width - right}" y2="{top + chart_h}" class="axis" />',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_h}" class="axis" />',
    ]
    legend_x = width - 450
    for idx, algorithm in enumerate(ALGORITHMS):
        algo_values = [100 * gap for gap in gap_by_algorithm[algorithm]]
        mean = statistics.mean(algo_values) if algo_values else 0.0
        std = statistics.stdev(algo_values) if len(algo_values) > 1 else 0.0
        x = legend_x + idx * 220
        lines.append(
            f'<rect x="{x}" y="18" width="14" height="14" fill="{_hist_color(algorithm)}" />'
            f'<text x="{x + 20}" y="30" class="label">{algorithm}</text>'
            f'<text x="{x}" y="49" class="label">mean {mean:.2f}%, std {std:.2f}%</text>'
        )

    for bin_idx in range(bins):
        base_x = left + bin_idx * group_w + group_w * 0.15
        for algo_idx, algorithm in enumerate(ALGORITHMS):
            count = counts[algorithm][bin_idx]
            h = chart_h * count / max_count
            x = base_x + algo_idx * bar_w
            y = top + chart_h - h
            lines.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{max(1.0, h):.2f}" fill="{_hist_color(algorithm)}" />'
            )
    for tick in range(6):
        value = lo + (hi - lo) * tick / 5
        x = left + chart_w * tick / 5
        lines.append(f'<text x="{x:.2f}" y="{top + chart_h + 22}" text-anchor="middle" class="label">{value:.1f}%</text>')
    lines.append(f'<text x="14" y="{top + 12}" class="label">max {max_count}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_combined_histogram(path: Path, scenario_gaps: dict[str, dict[str, list[float]]], bins: int) -> None:
    scenarios = sorted(scenario_gaps, key=_scenario_sort_key)
    if not any(gaps for by_algo in scenario_gaps.values() for gaps in by_algo.values()):
        return

    cell_w = 520
    cell_h = 330
    cols = 3
    rows = math.ceil(len(scenarios) / cols)
    width = cols * cell_w
    height = rows * cell_h + 56
    margin_x = 56
    margin_top = 62
    chart_w = cell_w - 92
    chart_h = cell_h - 132

    def esc(text: object) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:24px;font-weight:700}.subtitle{font-size:16px;font-weight:700}.label{font-size:11px}.axis{stroke:#374151;stroke-width:1}</style>',
        '<text x="32" y="34" class="title">Accepted-Reward Gap Histograms by Scenario</text>',
    ]
    legend_x = width - 360
    for idx, algorithm in enumerate(ALGORITHMS):
        x = legend_x + idx * 165
        lines.append(
            f'<rect x="{x}" y="20" width="14" height="14" fill="{_hist_color(algorithm)}" />'
            f'<text x="{x + 20}" y="32" class="label">{algorithm}</text>'
        )

    for scenario_idx, scenario in enumerate(scenarios):
        col = scenario_idx % cols
        row = scenario_idx // cols
        cell_x = col * cell_w
        cell_y = 56 + row * cell_h
        left = cell_x + margin_x
        top = cell_y + margin_top
        gap_by_algorithm = scenario_gaps[scenario]
        values = [100 * gap for gaps in gap_by_algorithm.values() for gap in gaps]
        if not values:
            continue
        lo = min(values)
        hi = max(values)
        if math.isclose(lo, hi):
            lo -= 0.5
            hi += 0.5
        step = (hi - lo) / bins
        counts: dict[str, list[int]] = {}
        for algorithm, gaps in gap_by_algorithm.items():
            bucket = [0] * bins
            for gap in gaps:
                value = 100 * gap
                bucket[min(bins - 1, max(0, int((value - lo) / step)))] += 1
            counts[algorithm] = bucket
        max_count = max(max(bucket) for bucket in counts.values()) or 1
        group_w = chart_w / bins
        bar_w = max(1.0, group_w * 0.7 / len(ALGORITHMS))

        lines.append(f'<text x="{left}" y="{cell_y + 25}" class="subtitle">{esc(scenario)}</text>')
        for idx, algorithm in enumerate(ALGORITHMS):
            algo_values = [100 * gap for gap in gap_by_algorithm[algorithm]]
            mean = statistics.mean(algo_values) if algo_values else 0.0
            std = statistics.stdev(algo_values) if len(algo_values) > 1 else 0.0
            lines.append(
                f'<text x="{left + idx * 210}" y="{cell_y + 45}" class="label">'
                f'{algorithm}: mean {mean:.2f}%, std {std:.2f}%</text>'
            )
        lines.append(f'<line x1="{left}" y1="{top + chart_h}" x2="{left + chart_w}" y2="{top + chart_h}" class="axis" />')
        lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_h}" class="axis" />')
        for bin_idx in range(bins):
            base_x = left + bin_idx * group_w + group_w * 0.15
            for algo_idx, algorithm in enumerate(ALGORITHMS):
                count = counts[algorithm][bin_idx]
                h = chart_h * count / max_count
                x = base_x + algo_idx * bar_w
                y = top + chart_h - h
                lines.append(
                    f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{max(1.0, h):.2f}" fill="{_hist_color(algorithm)}" />'
                )
        for tick in range(3):
            value = lo + (hi - lo) * tick / 2
            x = left + chart_w * tick / 2
            lines.append(f'<text x="{x:.2f}" y="{top + chart_h + 18}" text-anchor="middle" class="label">{value:.1f}%</text>')
        lines.append(f'<text x="{left - 42}" y="{top + 10}" class="label">max {max_count}</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hist_color(algorithm: str) -> str:
    return {
        "algo_naive": "#64748b",
        "algo_union": "#0891b2",
    }[algorithm]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and benchmark 128-instance scenario studies.")
    parser.add_argument("--root", default="data/scenario_study", help="output root for generated scenarios")
    parser.add_argument("--scenario", action="append", choices=sorted(CONFIGS, key=_scenario_sort_key), help="scenario to run; repeatable")
    parser.add_argument("--instances", type=int, default=128)
    parser.add_argument("--seed", type=int, default=114200)
    parser.add_argument("--generate-workers", type=int, default=8)
    parser.add_argument("--algorithm-workers", type=int, default=14)
    parser.add_argument(
        "--pipeline-workers",
        type=int,
        default=0,
        help="run each instance as one parallel job: ip_solver -> algo_naive -> algo_union; 0 keeps staged mode",
    )
    parser.add_argument("--union-seconds", type=float, default=10.0)
    parser.add_argument("--ip-time-limit", type=int, default=None)
    parser.add_argument("--ip-threads", type=int, default=1, help="Gurobi threads per IP job; use 0 for Gurobi default")
    parser.add_argument("--hist-bins", type=int, default=20)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-ip", action="store_true")
    parser.add_argument("--skip-algorithms", action="store_true")
    parser.add_argument("--force-generate", action="store_true")
    parser.add_argument("--force-ip", action="store_true")
    parser.add_argument("--force-algorithms", action="store_true")
    args = parser.parse_args()

    scenarios = tuple(args.scenario or DEFAULT_SCENARIOS)
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    print(f"scenario study root={root} scenarios={','.join(scenarios)} instances={args.instances}", flush=True)

    if not args.skip_generate:
        generate_instances(root, scenarios, args.instances, args.seed, args.generate_workers, args.force_generate)
    ip_threads = args.ip_threads if args.ip_threads > 0 else None
    if args.pipeline_workers > 0:
        if args.skip_ip or args.skip_algorithms:
            print("pipeline mode: skip flags will omit the matching per-instance stages", flush=True)
        run_instance_pipelines(
            root,
            scenarios,
            args.pipeline_workers,
            args.force_ip,
            args.force_algorithms,
            args.ip_time_limit,
            ip_threads,
            args.union_seconds,
            run_ip_stage=not args.skip_ip,
            run_algorithm_stage=not args.skip_algorithms,
        )
        add_ip_rows(root, scenarios)
    else:
        if not args.skip_ip:
            run_ip(root, scenarios, args.force_ip, args.ip_time_limit, ip_threads)
            add_ip_rows(root, scenarios)
        if not args.skip_algorithms:
            run_algorithms(root, scenarios, args.algorithm_workers, args.force_algorithms, args.union_seconds)
    summarize_results(root, scenarios, args.hist_bins)
    print(f"wrote {root / 'scenario_gap_summary.csv'}", flush=True)
    for scenario in scenarios:
        print(f"wrote {root / scenario / 'optimal_gap_histogram.svg'}", flush=True)


if __name__ == "__main__":
    main()
