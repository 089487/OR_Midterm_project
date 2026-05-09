from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithm_module import heuristic_algorithm
from heuristic_algo2 import heuristic_algorithm2
from heuristic_algo3 import heuristic_algorithm3
from heuristic_algo4 import heuristic_algorithm4
from mtp_common import parse_instance


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def default_instances(generated_dir: str) -> list[Path]:
    public = [ROOT / f"data/instance{i:02d}.txt" for i in range(1, 6)]
    generated = sorted(resolve_path(generated_dir).glob("*.txt"))
    return public + generated


def score(path: str | Path, assignment: list[int], relocation: list[list]) -> dict:
    inst = parse_instance(path)
    accepted = [order for order in inst.orders if assignment[order.id - 1]]
    rejected = [order for order in inst.orders if not assignment[order.id - 1]]
    sales = sum(order.revenue for order in accepted)
    moving = sum(row[5] for row in relocation)
    return {
        "accepted": len(accepted),
        "orders": inst.n_orders,
        "sales": sales,
        "profit": sales - 2 * sum(order.revenue for order in rejected),
        "moving": moving,
        "budget": inst.moving_budget,
    }


def run_method(name: str, path: Path, func: Callable[[Path], tuple[list[int], list[list]]]) -> dict:
    start = time.perf_counter()
    assignment, relocation = func(path)
    seconds = time.perf_counter() - start
    result = score(path, assignment, relocation)
    return {"instance": str(path), "method": name, "seconds": seconds, **result}


def write_outputs(rows: list[dict], out_dir: Path, total_seconds: float, time_limit: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "algo1234_comparison.csv"
    md_path = out_dir / "algo1234_comparison.md"

    fieldnames = [
        "instance",
        "method",
        "profit",
        "accepted",
        "orders",
        "sales",
        "moving",
        "budget",
        "seconds",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    by_instance: dict[str, list[dict]] = {}
    for row in rows:
        by_instance.setdefault(row["instance"], []).append(row)

    with md_path.open("w", encoding="utf-8") as fp:
        fp.write("# Algo1 / Algo2 / Algo3 / Algo4 Comparison\n\n")
        fp.write(f"Per-testcase time limit for timed heuristics: `{time_limit:.0f}s`.\n\n")
        fp.write(f"Total benchmark wall time: `{total_seconds:.2f}s`.\n\n")
        fp.write("## Algorithm Summary\n\n")
        fp.write(
            "- **Algo1**: greedy insertion baseline. Orders are sorted by descending revenue; "
            "each order is inserted into the feasible car route with the smallest extra relocation cost.\n"
        )
        fp.write(
            "- **Algo2**: order-node DP trajectory heuristic. For each car ordering/lambda setting, "
            "it finds a high-score route over currently unassigned orders with normalized reward and relocation penalty, "
            "then masks selected orders.\n"
        )
        fp.write(
            "- **Algo3**: Algo1 plus batch-ratio repair. It starts from Algo1, samples up to five low-efficiency trajectories, "
            "releases them, shuffles those cars, and rebuilds them with a top-10 station DP scored by "
            "`sumR / (1 + sum_move)`; worse full solutions are rolled back.\n\n"
        )
        fp.write(
            "- **Algo4**: Algo1 plus local IP repair. It samples low-efficiency trajectories, releases those cars, "
            "then solves a capped small arc-flow IP over the released cars and candidate unassigned orders.\n\n"
        )
        fp.write("## Results\n\n")
        fp.write("| Instance | Algo1 | Algo2 | Algo3 | Algo4 | Best |\n")
        fp.write("| --- | ---: | ---: | ---: | ---: | --- |\n")
        for instance, instance_rows in by_instance.items():
            best = max(instance_rows, key=lambda row: (row["profit"], -row["seconds"]))
            by_method = {row["method"]: row for row in instance_rows}
            algo1 = by_method["algo1"]
            algo2 = by_method["algo2"]
            algo3 = by_method["algo3"]
            algo4 = by_method["algo4"]
            fp.write(
                f"| `{instance}` | {_format_cell(algo1, best)} | {_format_cell(algo2, best)} | "
                f"{_format_cell(algo3, best)} | {_format_cell(algo4, best)} | {best['method']} |\n"
            )

    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


def _format_cell(row: dict, best: dict) -> str:
    profit = str(row["profit"])
    if row["profit"] == best["profit"]:
        profit = f"**{profit}**"
    return (
        f"{profit}<br>"
        f"{row['accepted']}/{row['orders']} orders<br>"
        f"{row['moving']}/{row['budget']} move<br>"
        f"{row['seconds']:.2f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="*")
    parser.add_argument("--generated-dir", default="experiments/generated_data_smoke")
    parser.add_argument("--time-limit", type=float, default=140.0)
    parser.add_argument("--seed", type=int, default=1142)
    parser.add_argument("--out-dir", default="experiments/benchmark_results")
    parser.add_argument("--algo4-candidate-order-limit", type=int, default=160)
    parser.add_argument("--algo4-per-ip-seconds", type=float, default=0.5)
    parser.add_argument(
        "--algo4-max-no-improve",
        type=int,
        default=0,
        help="stop Algo4 after this many non-improving repairs; 0 disables this guard",
    )
    args = parser.parse_args()

    instances = [resolve_path(path) for path in args.instances] if args.instances else default_instances(args.generated_dir)
    methods: list[tuple[str, Callable[[Path], tuple[list[int], list[list]]]]] = [
        ("algo1", lambda path: heuristic_algorithm(path, raw_test=True)),
        (
            "algo2",
            lambda path: heuristic_algorithm2(
                path,
                raw_test=True,
                seed=args.seed,
                max_seconds=args.time_limit,
            ),
        ),
        (
            "algo3",
            lambda path: heuristic_algorithm3(
                path,
                raw_test=True,
                seed=args.seed,
                max_seconds=args.time_limit,
            ),
        ),
        (
            "algo4",
            lambda path: heuristic_algorithm4(
                path,
                raw_test=True,
                seed=args.seed,
                max_seconds=args.time_limit,
                candidate_order_limit=args.algo4_candidate_order_limit,
                per_ip_seconds=args.algo4_per_ip_seconds,
                max_no_improve=args.algo4_max_no_improve,
            ),
        ),
    ]

    rows: list[dict] = []
    total_start = time.perf_counter()
    for path in instances:
        print(f"\n{path}", flush=True)
        for name, func in methods:
            row = run_method(name, path, func)
            rows.append(row)
            print(
                f"  {name:<5} profit={row['profit']:>12} "
                f"accepted={row['accepted']:>5}/{row['orders']:<5} "
                f"moving={row['moving']:>8}/{row['budget']:<8} "
                f"time={row['seconds']:>8.2f}s",
                flush=True,
            )

    total_seconds = time.perf_counter() - total_start
    write_outputs(rows, resolve_path(args.out_dir), total_seconds, args.time_limit)
    print(f"Total benchmark wall time: {total_seconds:.2f}s")


if __name__ == "__main__":
    main()
