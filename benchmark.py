from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Iterable

from mtp_common import Instance, parse_instance


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
    args = parser.parse_args()

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
