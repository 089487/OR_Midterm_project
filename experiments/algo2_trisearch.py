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


def evaluate_lambda(
    path: Path,
    lam: float,
    cache: dict[float, dict],
    *,
    max_seconds: float,
    seed: int,
) -> dict:
    key = round(lam, 12)
    if key in cache:
        return cache[key]

    start = time.perf_counter()
    assignment, relocation = heuristic_algorithm2(
        path,
        lambdas=[lam],
        seed=seed,
        max_seconds=max_seconds,
        raw_test=True,
    )
    elapsed = time.perf_counter() - start
    result = score(path, assignment, relocation)
    row = {
        "lambda": lam,
        "profit": result["profit"],
        "accepted": result["accepted"],
        "orders": result["orders"],
        "sales": result["sales"],
        "moving": result["moving"],
        "budget": result["budget"],
        "seconds": elapsed,
    }
    cache[key] = row
    return row


def ternary_search_instance(
    path: Path,
    *,
    low: float,
    high: float,
    iterations: int,
    max_seconds: float,
    seed: int,
) -> tuple[list[dict], dict]:
    cache: dict[float, dict] = {}
    rows: list[dict] = []
    lo = low
    hi = high

    for iteration in range(1, iterations + 1):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        left = evaluate_lambda(path, m1, cache, max_seconds=max_seconds, seed=seed)
        right = evaluate_lambda(path, m2, cache, max_seconds=max_seconds, seed=seed)

        if left["profit"] < right["profit"]:
            decision = "right"
            lo = m1
        else:
            decision = "left"
            hi = m2

        rows.append(
            {
                "iteration": iteration,
                "lo": lo,
                "hi": hi,
                "m1": m1,
                "m2": m2,
                "m1_profit": left["profit"],
                "m2_profit": right["profit"],
                "m1_seconds": left["seconds"],
                "m2_seconds": right["seconds"],
                "decision": decision,
            }
        )

    best = max(cache.values(), key=lambda row: (row["profit"], -row["moving"], row["accepted"]))
    return rows, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="*")
    parser.add_argument("--generated-dir", default="experiments/generated_data_smoke")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--low", type=float, default=0.0)
    parser.add_argument("--high", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=1142)
    parser.add_argument("--max-seconds", type=float, default=1800.0)
    parser.add_argument("--out-dir", default="experiments/benchmark_results")
    args = parser.parse_args()

    instances = [resolve_path(path) for path in args.instances] if args.instances else default_instances(args.generated_dir)
    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "algo2_trisearch.csv"
    md_path = out_dir / "algo2_trisearch.md"

    all_rows: list[dict] = []
    best_rows: list[dict] = []
    total_start = time.perf_counter()

    for path in instances:
        print(f"\n{path}", flush=True)
        instance_start = time.perf_counter()
        rows, best = ternary_search_instance(
            path,
            low=args.low,
            high=args.high,
            iterations=args.iterations,
            max_seconds=args.max_seconds,
            seed=args.seed,
        )
        instance_seconds = time.perf_counter() - instance_start
        for row in rows:
            row = {"instance": str(path), **row}
            all_rows.append(row)
            print(
                f"  iter={row['iteration']:02d} m1={row['m1']:.8f} "
                f"p1={row['m1_profit']:>12} m2={row['m2']:.8f} "
                f"p2={row['m2_profit']:>12} keep={row['decision']}",
                flush=True,
            )
        best_row = {
            "instance": str(path),
            "best_lambda": best["lambda"],
            "profit": best["profit"],
            "accepted": best["accepted"],
            "orders": best["orders"],
            "sales": best["sales"],
            "moving": best["moving"],
            "budget": best["budget"],
            "instance_seconds": instance_seconds,
        }
        best_rows.append(best_row)
        print(
            f"  BEST lambda={best['lambda']:.8f} profit={best['profit']} "
            f"accepted={best['accepted']}/{best['orders']} "
            f"moving={best['moving']}/{best['budget']} "
            f"time={instance_seconds:.2f}s",
            flush=True,
        )

    total_seconds = time.perf_counter() - total_start

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        fieldnames = [
            "instance",
            "iteration",
            "lo",
            "hi",
            "m1",
            "m2",
            "m1_profit",
            "m2_profit",
            "m1_seconds",
            "m2_seconds",
            "decision",
        ]
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    with md_path.open("w", encoding="utf-8") as fp:
        fp.write("# Algo2 Ternary Search Benchmark\n\n")
        fp.write(f"Search interval: `[{args.low}, {args.high}]`\n\n")
        fp.write(f"Iterations per instance: `{args.iterations}`\n\n")
        fp.write(f"Max seconds per lambda run: `{args.max_seconds}`\n\n")
        fp.write(f"Total benchmark time: `{total_seconds:.2f}` seconds\n\n")
        fp.write("## Best By Instance\n\n")
        fp.write("| Instance | Best Lambda | Profit | Accepted | Moving | Seconds |\n")
        fp.write("| --- | ---: | ---: | ---: | ---: | ---: |\n")
        for row in best_rows:
            fp.write(
                f"| `{row['instance']}` | {row['best_lambda']:.8f} | {row['profit']} | "
                f"{row['accepted']}/{row['orders']} | {row['moving']}/{row['budget']} | "
                f"{row['instance_seconds']:.2f} |\n"
            )
        fp.write("\n## Iterations\n\n")
        fp.write("| Instance | Iter | m1 | p1 | sec1 | m2 | p2 | sec2 | Keep |\n")
        fp.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n")
        for row in all_rows:
            fp.write(
                f"| `{row['instance']}` | {row['iteration']} | {row['m1']:.8f} | "
                f"{row['m1_profit']} | {row['m1_seconds']:.2f} | {row['m2']:.8f} | "
                f"{row['m2_profit']} | {row['m2_seconds']:.2f} | {row['decision']} |\n"
            )

    print(f"\nWrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Total benchmark time: {total_seconds:.2f}s")


if __name__ == "__main__":
    main()
