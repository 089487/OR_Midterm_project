from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithm_module import heuristic_algorithm
from heuristic_algo2 import heuristic_algorithm2
from ip_solver import solve_instance
from mtp_common import parse_instance


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def score(path: str | Path, assignment: list[int], relocation: list[list]) -> dict:
    inst = parse_instance(path)
    accepted = [order for order in inst.orders if assignment[order.id - 1]]
    rejected = [order for order in inst.orders if not assignment[order.id - 1]]
    sales = sum(order.revenue for order in accepted)
    profit = sales - 2 * sum(order.revenue for order in rejected)
    moving = sum(row[5] for row in relocation)
    return {
        "accepted": len(accepted),
        "orders": inst.n_orders,
        "sales": sales,
        "profit": profit,
        "moving": moving,
        "budget": inst.moving_budget,
    }


def run_method(name: str, func, path: str | Path) -> dict:
    start = time.perf_counter()
    assignment, relocation = func(path)
    elapsed = time.perf_counter() - start
    result = score(path, assignment, relocation)
    result["method"] = name
    result["seconds"] = elapsed
    return result


def run_ip(path: str | Path, time_limit: int) -> dict:
    start = time.perf_counter()
    solution = solve_instance(path, time_limit=time_limit, verbose=False)
    elapsed = time.perf_counter() - start
    result = score(path, solution["assignment"], solution["relocations"])
    result["method"] = f"IP({time_limit}s)"
    result["seconds"] = elapsed
    return result


def print_result(instance: str, result: dict, best_profit: int | None = None) -> None:
    gap = "" if best_profit is None else f", gap={best_profit - result['profit']}"
    print(
        f"{instance:34s} {result['method']:10s} "
        f"profit={result['profit']:12d}{gap:>14s} "
        f"accepted={result['accepted']:5d}/{result['orders']:<5d} "
        f"moving={result['moving']:8d}/{result['budget']:<8d} "
        f"time={result['seconds']:7.2f}s",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-dir", default="experiments/generated_data_smoke")
    parser.add_argument("--ip-time-limit", type=int, default=30)
    parser.add_argument("--algo2-seconds", type=float, default=30)
    args = parser.parse_args()

    public = [ROOT / f"data/instance{i:02d}.txt" for i in range(1, 6)]
    generated = sorted(resolve_path(args.generated_dir).glob("*.txt"))

    print("Public instances", flush=True)
    for path in public:
        ip = run_ip(path, args.ip_time_limit)
        best = ip["profit"]
        print_result(path.name, ip, best)
        print_result(path.name, run_method("algo(raw)", lambda p: heuristic_algorithm(p, raw_test=True), path), best)
        print_result(
            path.name,
            run_method(
                "algo2(raw)",
                lambda p: heuristic_algorithm2(p, raw_test=True, max_seconds=args.algo2_seconds),
                path,
            ),
            best,
        )

    if generated:
        print("\nGenerated instances", flush=True)
    for path in generated:
        inst = parse_instance(path)
        ip = None
        if inst.n_orders <= 150 and inst.n_cars <= 100:
            try:
                ip = run_ip(path, args.ip_time_limit)
            except Exception as exc:
                print(f"{path.name:34s} IP skipped/error: {exc}", flush=True)
        best = ip["profit"] if ip else None
        if ip:
            print_result(path.name, ip, best)
        else:
            print(f"{path.name:34s} IP         skipped", flush=True)
        print_result(path.name, run_method("algo(raw)", lambda p: heuristic_algorithm(p, raw_test=True), path), best)
        print_result(
            path.name,
            run_method(
                "algo2(raw)",
                lambda p: heuristic_algorithm2(p, raw_test=True, max_seconds=args.algo2_seconds),
                path,
            ),
            best,
        )


if __name__ == "__main__":
    main()
