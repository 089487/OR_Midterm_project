from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from heuristic_algo2 import heuristic_algorithm2
from mtp_common import parse_instance


LAMBDA_L = [[0, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0]]


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


def default_instances(generated_dir: str) -> list[Path]:
    public = [ROOT / f"data/instance{i:02d}.txt" for i in range(1, 6)]
    generated = sorted(resolve_path(generated_dir).glob("*.txt"))
    return public + generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="*")
    parser.add_argument("--generated-dir", default="experiments/generated_data_smoke")
    parser.add_argument("--max-seconds", type=float, default=1800.0)
    parser.add_argument("--out-dir", default="experiments/benchmark_results")
    parser.add_argument("--raw-test", action="store_true", default=True)
    args = parser.parse_args()

    instances = [resolve_path(path) for path in args.instances] if args.instances else default_instances(args.generated_dir)
    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "lambda_benchmark.csv"
    md_path = out_dir / "lambda_benchmark.md"

    rows: list[dict] = []
    total_start = time.perf_counter()
    for path in instances:
        inst = parse_instance(path)
        print(f"\n{path}", flush=True)
        instance_start = time.perf_counter()
        best_row = None
        for lambda_group_id, lambdas in enumerate(LAMBDA_L, start=1):
            for lam in lambdas:
                start = time.perf_counter()
                assignment, relocation = heuristic_algorithm2(
                    path,
                    lambdas=[lam],
                    max_seconds=args.max_seconds,
                    raw_test=True,
                )
                elapsed = time.perf_counter() - start
                result = score(path, assignment, relocation)
                row = {
                    "instance": str(path),
                    "lambda_group": lambda_group_id,
                    "lambda": lam,
                    "profit": result["profit"],
                    "accepted": result["accepted"],
                    "orders": result["orders"],
                    "sales": result["sales"],
                    "moving": result["moving"],
                    "budget": result["budget"],
                    "seconds": elapsed,
                }
                rows.append(row)
                if best_row is None or row["profit"] > best_row["profit"]:
                    best_row = row
                print(
                    f"  lambda={lam:<4} profit={result['profit']:>12} "
                    f"accepted={result['accepted']:>5}/{inst.n_orders:<5} "
                    f"moving={result['moving']:>8}/{inst.moving_budget:<8} "
                    f"time={elapsed:>8.2f}s",
                    flush=True,
                )
        instance_elapsed = time.perf_counter() - instance_start
        if best_row is not None:
            print(
                f"  BEST lambda={best_row['lambda']} profit={best_row['profit']} "
                f"time_total_for_instance={instance_elapsed:.2f}s",
                flush=True,
            )

    total_elapsed = time.perf_counter() - total_start

    fieldnames = [
        "instance",
        "lambda_group",
        "lambda",
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

    with md_path.open("w", encoding="utf-8") as fp:
        fp.write("# Lambda Benchmark\n\n")
        fp.write(f"Max seconds per lambda run: `{args.max_seconds}`\n\n")
        fp.write(f"Total benchmark time: `{total_elapsed:.2f}` seconds\n\n")
        fp.write("| Instance | Lambda | Profit | Accepted | Moving | Seconds |\n")
        fp.write("| --- | ---: | ---: | ---: | ---: | ---: |\n")
        for row in rows:
            fp.write(
                f"| `{row['instance']}` | {row['lambda']} | {row['profit']} | "
                f"{row['accepted']}/{row['orders']} | {row['moving']}/{row['budget']} | "
                f"{row['seconds']:.2f} |\n"
            )
        fp.write("\n## Best By Instance\n\n")
        fp.write("| Instance | Best Lambda | Profit | Accepted | Moving |\n")
        fp.write("| --- | ---: | ---: | ---: | ---: |\n")
        for path in instances:
            instance_rows = [row for row in rows if row["instance"] == str(path)]
            if not instance_rows:
                continue
            best = max(instance_rows, key=lambda row: row["profit"])
            fp.write(
                f"| `{path}` | {best['lambda']} | {best['profit']} | "
                f"{best['accepted']}/{best['orders']} | {best['moving']}/{best['budget']} |\n"
            )

    print(f"\nWrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Total benchmark time: {total_elapsed:.2f}s")


if __name__ == "__main__":
    main()
