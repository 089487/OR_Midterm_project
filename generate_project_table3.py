from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from mtp_common import parse_instance


FIELDNAMES = [
    "scenario",
    "instances",
    "base_gap_mean_pct",
    "base_gap_std_pct",
    "union_optimal_gap_mean_pct",
    "union_optimal_gap_std_pct",
    "union_improve_gap_mean_pct",
    "union_improve_gap_std_pct",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


def scenario_sort_key(path: Path) -> tuple[int, str]:
    name = path.name
    if name.startswith("S") and name[1:].isdigit():
        return int(name[1:]), name
    return 9999, name


def total_reward(instance_path: Path) -> int:
    inst = parse_instance(instance_path)
    return sum(order.revenue for order in inst.orders)


def summarize(root: Path) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = []
    for scenario_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=scenario_sort_key):
        bench_path = scenario_dir / "benchmark_results.csv"
        if not bench_path.exists():
            continue

        rows = [row for row in read_rows(bench_path) if row.get("status") == "ok"]
        by_instance: dict[str, dict[str, dict[str, str]]] = {}
        for row in rows:
            by_instance.setdefault(row["instance"], {})[row["algorithm"]] = row

        base_gaps: list[float] = []
        union_gaps: list[float] = []
        improve_gaps: list[float] = []
        for instance_name, algos in sorted(by_instance.items()):
            required = ("ip_solver", "algo_naive", "algo_union")
            if any(algo not in algos for algo in required):
                continue

            total = total_reward(scenario_dir / instance_name)
            ip_profit = float(algos["ip_solver"]["profit"])
            base_profit = float(algos["algo_naive"]["profit"])
            union_profit = float(algos["algo_union"]["profit"])

            ip_reward3 = ip_profit + 2 * total
            base_reward3 = base_profit + 2 * total
            if ip_reward3 <= 0 or base_reward3 <= 0:
                continue

            base_gaps.append(100.0 * (ip_profit - base_profit) / ip_reward3)
            union_gaps.append(100.0 * (ip_profit - union_profit) / ip_reward3)
            improve_gaps.append(100.0 * (union_profit - base_profit) / base_reward3)

        base_mean, base_std = mean_std(base_gaps)
        union_mean, union_std = mean_std(union_gaps)
        improve_mean, improve_std = mean_std(improve_gaps)
        output_rows.append(
            {
                "scenario": scenario_dir.name,
                "instances": len(base_gaps),
                "base_gap_mean_pct": round(base_mean, 6),
                "base_gap_std_pct": round(base_std, 6),
                "union_optimal_gap_mean_pct": round(union_mean, 6),
                "union_optimal_gap_std_pct": round(union_std, 6),
                "union_improve_gap_mean_pct": round(improve_mean, 6),
                "union_improve_gap_std_pct": round(improve_std, 6),
            }
        )
    return output_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def latex_table(rows: list[dict[str, object]]) -> str:
    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Scenario & Baseline gap (\%) & Proposed gap (\%) & Improvement over baseline (\%)\\",
        r"& $\mu \pm \sigma$ & $\mu \pm \sigma$ & $\mu \pm \sigma$\\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['scenario']:<3} & "
            f"${float(row['base_gap_mean_pct']):.2f} \\pm {float(row['base_gap_std_pct']):.2f}$ & "
            f"${float(row['union_optimal_gap_mean_pct']):.2f} \\pm {float(row['union_optimal_gap_std_pct']):.2f}$ & "
            f"${float(row['union_improve_gap_mean_pct']):.2f} \\pm {float(row['union_improve_gap_std_pct']):.2f}$\\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{All-scenario benchmark for the 10-second proposed method.",
            r"Each row summarizes 30 generated instances. Baseline gap and proposed gap",
            r"are measured against the exact IP upper benchmark using accepted reward;",
            r"improvement is the proposed method's accepted-reward gain over the",
            r"chronological baseline.}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/exp_instances")
    parser.add_argument("--csv", default="data/exp_instances/summary/project_table3.csv")
    parser.add_argument("--tex", default="data/exp_instances/summary/project_table3.tex")
    args = parser.parse_args()

    rows = summarize(Path(args.root))
    write_csv(Path(args.csv), rows)
    Path(args.tex).parent.mkdir(parents=True, exist_ok=True)
    Path(args.tex).write_text(latex_table(rows), encoding="utf-8")
    print(f"wrote {args.csv}")
    print(f"wrote {args.tex}")


if __name__ == "__main__":
    main()
