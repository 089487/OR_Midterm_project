from __future__ import annotations

import argparse
import csv
from pathlib import Path


ALGORITHMS = ("algo1", "algo5")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _to_float(value: str) -> float:
    return float(value) if value not in ("", None) else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _scenario_sort_key(path: Path) -> tuple[int, str]:
    name = path.name
    if name.startswith("S") and name[1:].isdigit():
        return int(name[1:]), name
    return 9999, name


def summarize(root: Path, out_dir: Path) -> tuple[Path, Path, Path]:
    scenario_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []

    for scenario_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=_scenario_sort_key):
        bench_path = scenario_dir / "benchmark_results.csv"
        if not bench_path.exists():
            continue

        rows = _read_rows(bench_path)
        by_instance: dict[str, dict[str, dict[str, str]]] = {}
        for row in rows:
            if row.get("status") != "ok":
                continue
            by_instance.setdefault(row["instance"], {})[row["algorithm"]] = row

        algo_stats = {
            algo: {
                "gap": [],
                "gap_pct": [],
                "profit": [],
                "moving_time": [],
                "execution_time": [],
                "wins_vs_other": 0,
                "ties_vs_other": 0,
            }
            for algo in ALGORITHMS
        }
        ip_profit_values: list[float] = []
        ip_time_values: list[float] = []
        algo1_wins = 0
        algo5_wins = 0
        ties = 0
        completed_instances = 0

        for instance, algos in sorted(by_instance.items()):
            if "ip_solver" not in algos or any(algo not in algos for algo in ALGORITHMS):
                continue
            completed_instances += 1
            ip_profit = _to_float(algos["ip_solver"]["profit"])
            ip_time = _to_float(algos["ip_solver"]["execution_time"])
            ip_profit_values.append(ip_profit)
            ip_time_values.append(ip_time)

            profits = {algo: _to_float(algos[algo]["profit"]) for algo in ALGORITHMS}
            if profits["algo1"] > profits["algo5"]:
                algo1_wins += 1
            elif profits["algo5"] > profits["algo1"]:
                algo5_wins += 1
            else:
                ties += 1

            for algo in ALGORITHMS:
                profit = profits[algo]
                gap = ip_profit - profit
                gap_pct = gap / abs(ip_profit) if ip_profit != 0 else 0.0
                algo_stats[algo]["gap"].append(gap)
                algo_stats[algo]["gap_pct"].append(gap_pct)
                algo_stats[algo]["profit"].append(profit)
                algo_stats[algo]["moving_time"].append(_to_float(algos[algo]["moving_time"]))
                algo_stats[algo]["execution_time"].append(_to_float(algos[algo]["execution_time"]))

                comparison_rows.append(
                    {
                        "scenario": scenario_dir.name,
                        "instance": instance,
                        "algorithm": algo,
                        "ip_profit": round(ip_profit, 6),
                        "algorithm_profit": round(profit, 6),
                        "profit_gap": round(gap, 6),
                        "optimal_gap_pct": round(100.0 * gap_pct, 6),
                        "moving_time": algos[algo]["moving_time"],
                        "execution_time": algos[algo]["execution_time"],
                        "ip_execution_time": algos["ip_solver"]["execution_time"],
                    }
                )

        row: dict[str, object] = {
            "scenario": scenario_dir.name,
            "instances": completed_instances,
            "ip_avg_profit": round(_mean(ip_profit_values), 6),
            "ip_avg_execution_time": round(_mean(ip_time_values), 6),
            "algo1_wins": algo1_wins,
            "algo5_wins": algo5_wins,
            "ties": ties,
        }

        for algo in ALGORITHMS:
            stats = algo_stats[algo]
            row[f"{algo}_avg_profit"] = round(_mean(stats["profit"]), 6)
            row[f"{algo}_avg_profit_gap"] = round(_mean(stats["gap"]), 6)
            row[f"{algo}_avg_optimal_gap_pct"] = round(100.0 * _mean(stats["gap_pct"]), 6)
            row[f"{algo}_avg_moving_time"] = round(_mean(stats["moving_time"]), 6)
            row[f"{algo}_avg_execution_time"] = round(_mean(stats["execution_time"]), 6)

        scenario_rows.append(row)

    summary_path = out_dir / "scenario_summary.csv"
    detail_path = out_dir / "instance_gap_detail.csv"
    chart_path = out_dir / "scenario_algo_comparison.svg"

    summary_fields = [
        "scenario",
        "instances",
        "ip_avg_profit",
        "ip_avg_execution_time",
        "algo1_avg_profit",
        "algo1_avg_profit_gap",
        "algo1_avg_optimal_gap_pct",
        "algo1_avg_moving_time",
        "algo1_avg_execution_time",
        "algo5_avg_profit",
        "algo5_avg_profit_gap",
        "algo5_avg_optimal_gap_pct",
        "algo5_avg_moving_time",
        "algo5_avg_execution_time",
        "algo1_wins",
        "algo5_wins",
        "ties",
    ]
    detail_fields = [
        "scenario",
        "instance",
        "algorithm",
        "ip_profit",
        "algorithm_profit",
        "profit_gap",
        "optimal_gap_pct",
        "moving_time",
        "execution_time",
        "ip_execution_time",
    ]
    _write_csv(summary_path, scenario_rows, summary_fields)
    _write_csv(detail_path, comparison_rows, detail_fields)
    _plot_summary(scenario_rows, chart_path)
    return summary_path, detail_path, chart_path


def _plot_summary(rows: list[dict[str, object]], chart_path: Path) -> None:
    scenarios = [str(row["scenario"]) for row in rows]
    gap1 = [float(row["algo1_avg_optimal_gap_pct"]) for row in rows]
    gap5 = [float(row["algo5_avg_optimal_gap_pct"]) for row in rows]
    wins1 = [int(row["algo1_wins"]) for row in rows]
    wins5 = [int(row["algo5_wins"]) for row in rows]

    width = 1200
    height = 760
    margin_left = 70
    margin_right = 35
    top_gap = 70
    chart_h = 250
    chart_gap = 120
    bar_group_w = (width - margin_left - margin_right) / max(1, len(scenarios))
    bar_w = min(26, bar_group_w * 0.28)

    def esc(text: object) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def y_scale(value: float, values: list[float], top: float, h: float) -> float:
        lo = min(0.0, min(values) if values else 0.0)
        hi = max(0.0, max(values) if values else 1.0)
        if hi == lo:
            hi = lo + 1.0
        return top + (hi - value) / (hi - lo) * h

    def bar(value: float, all_values: list[float], x: float, y0: float, h: float, color: str) -> str:
        zero = y_scale(0, all_values, y0, h)
        y = y_scale(value, all_values, y0, h)
        rect_y = min(y, zero)
        rect_h = max(1.0, abs(zero - y))
        return f'<rect x="{x:.2f}" y="{rect_y:.2f}" width="{bar_w:.2f}" height="{rect_h:.2f}" fill="{color}" />'

    gap_values = gap1 + gap5
    win_values = wins1 + wins5 + [30]
    gap_zero = y_scale(0, gap_values, top_gap, chart_h)
    win_zero = y_scale(0, win_values, top_gap + chart_h + chart_gap, chart_h)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:22px;font-weight:700}.label{font-size:12px}.axis{stroke:#374151;stroke-width:1}.grid{stroke:#e5e7eb;stroke-width:1}.legend{font-size:13px}</style>',
        f'<text x="{margin_left}" y="32" class="title">Average Optimal Gap by Scenario</text>',
        f'<line x1="{margin_left}" y1="{gap_zero:.2f}" x2="{width - margin_right}" y2="{gap_zero:.2f}" class="axis" />',
        f'<line x1="{margin_left}" y1="{top_gap}" x2="{margin_left}" y2="{top_gap + chart_h}" class="axis" />',
        f'<text x="{margin_left}" y="{top_gap + chart_h + chart_gap - 45}" class="title">Head-to-Head Profit Wins</text>',
        f'<line x1="{margin_left}" y1="{win_zero:.2f}" x2="{width - margin_right}" y2="{win_zero:.2f}" class="axis" />',
        f'<line x1="{margin_left}" y1="{top_gap + chart_h + chart_gap}" x2="{margin_left}" y2="{top_gap + 2 * chart_h + chart_gap}" class="axis" />',
        f'<rect x="{width - 225}" y="18" width="14" height="14" fill="#2563eb" /><text x="{width - 205}" y="30" class="legend">algo1</text>',
        f'<rect x="{width - 145}" y="18" width="14" height="14" fill="#dc2626" /><text x="{width - 125}" y="30" class="legend">algo5</text>',
    ]

    scenarios = [str(row["scenario"]) for row in rows]
    for idx, scenario in enumerate(scenarios):
        center = margin_left + bar_group_w * idx + bar_group_w / 2
        lines.append(bar(gap1[idx], gap_values, center - bar_w - 2, top_gap, chart_h, "#2563eb"))
        lines.append(bar(gap5[idx], gap_values, center + 2, top_gap, chart_h, "#dc2626"))
        lines.append(f'<text x="{center:.2f}" y="{top_gap + chart_h + 20}" text-anchor="middle" class="label">{esc(scenario)}</text>')
        lines.append(bar(wins1[idx], win_values, center - bar_w - 2, top_gap + chart_h + chart_gap, chart_h, "#2563eb"))
        lines.append(bar(wins5[idx], win_values, center + 2, top_gap + chart_h + chart_gap, chart_h, "#dc2626"))
        lines.append(f'<text x="{center:.2f}" y="{top_gap + 2 * chart_h + chart_gap + 20}" text-anchor="middle" class="label">{esc(scenario)}</text>')

    gap_hi = max(gap_values) if gap_values else 0.0
    gap_lo = min(gap_values) if gap_values else 0.0
    lines.append(f'<text x="12" y="{top_gap + 14}" class="label">max {gap_hi:.1f}%</text>')
    lines.append(f'<text x="12" y="{top_gap + chart_h}" class="label">min {gap_lo:.1f}%</text>')
    lines.append(f'<text x="12" y="{top_gap + chart_h + chart_gap + 14}" class="label">30 wins</text>')
    lines.append(f'<text x="35" y="{top_gap + 2 * chart_h + chart_gap}" class="label">0</text>')
    lines.append("</svg>")
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize benchmark_results.csv by scenario.")
    parser.add_argument("--root", default="data/exp_instances")
    parser.add_argument("--out-dir", default="data/exp_instances/summary")
    args = parser.parse_args()

    summary_path, detail_path, chart_path = summarize(Path(args.root), Path(args.out_dir))
    print(f"wrote {summary_path}")
    print(f"wrote {detail_path}")
    print(f"wrote {chart_path}")


if __name__ == "__main__":
    main()
