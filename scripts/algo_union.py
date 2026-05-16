from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Any

from algo1 import heuristic_algorithm as algo1_heuristic
from algo5 import heuristic_algorithm as algo5_heuristic
from heuristic_algo3 import (
    _assignment_to_routes,
    _build_context,
    _moving_from_routes,
    _profit_from_routes,
    _routes_to_solution,
    _sample_routes_by_softmax_efficiency,
)
from mtp_common import Instance, parse_instance


def _accepted(car_id: object) -> bool:
    try:
        return int(car_id) > 0
    except (TypeError, ValueError):
        return False


def _normalize_assignment(inst: Instance, assignment: list[object]) -> list[int]:
    normalized = [0] * inst.n_orders
    valid_car_ids = {car.id for car in inst.cars}
    for idx, car_id in enumerate(assignment[: inst.n_orders]):
        if _accepted(car_id) and int(car_id) in valid_car_ids:
            normalized[idx] = int(car_id)
    return normalized


def _to_grading_output(assignment: list[object], relocation: list[list]) -> tuple[list[int], list[list]]:
    """Convert internal benchmark output to the official grading format.

    Internal solvers may use 0 for rejected orders and may store extra relocation
    fields such as arrival time, moving minutes, and reason. The official checker
    expects -1 for rejected orders and exactly:
    [car_id, from_station, to_station, departure_time].
    """
    grading_assignment = [int(car_id) if _accepted(car_id) else -1 for car_id in assignment]
    grading_relocation: list[list] = []
    for row in relocation:
        if len(row) < 4:
            continue
        grading_relocation.append([int(row[0]), int(row[1]), int(row[2]), str(row[3])])
    return grading_assignment, grading_relocation


def _profit_from_assignment(inst: Instance, assignment: list[int]) -> int:
    accepted_revenue = sum(
        order.revenue for order, car_id in zip(inst.orders, assignment) if _accepted(car_id)
    )
    total_revenue = sum(order.revenue for order in inst.orders)
    return accepted_revenue - 2 * (total_revenue - accepted_revenue)


def _algo4_helpers():
    from heuristic_algo4 import _select_candidate_orders, _solve_local_ip

    return _select_candidate_orders, _solve_local_ip


def pre_build(
    instance_file: str | Path = "data/instance05.txt",
    *args: Any,
    raw_test: bool = False,
    return_metadata: bool = False,
    **kwargs: Any,
):
    """Run Algo1 and Algo5, then keep the assignment with larger profit."""
    inst = parse_instance(instance_file)
    candidates = []

    a1_assignment, a1_relocation = algo1_heuristic(instance_file, raw_test=raw_test)
    a1_assignment = _normalize_assignment(inst, a1_assignment)
    candidates.append(
        {
            "source": "algo1",
            "assignment": a1_assignment,
            "relocation": a1_relocation,
            "profit": _profit_from_assignment(inst, a1_assignment),
        }
    )

    a5_assignment, a5_relocation = algo5_heuristic(instance_file, raw_test=raw_test)
    a5_assignment = _normalize_assignment(inst, a5_assignment)
    candidates.append(
        {
            "source": "algo5",
            "assignment": a5_assignment,
            "relocation": a5_relocation,
            "profit": _profit_from_assignment(inst, a5_assignment),
        }
    )

    best = max(candidates, key=lambda item: (item["profit"], item["source"] == "algo1"))
    if return_metadata:
        return best["assignment"], best["relocation"], {
            "source": best["source"],
            "profit": best["profit"],
            "candidates": {item["source"]: item["profit"] for item in candidates},
        }
    return best["assignment"], best["relocation"]


def small_ip_improve(
    instance_file: str | Path = "data/instance05.txt",
    assignment: list[object] | None = None,
    *,
    iterations: int = 100000,
    max_seconds: float = 100.0,
    seed: int = 1142,
    temperature: float = 0.35,
    batch_size: int = 5,
    candidate_order_limit: int = 160,
    per_ip_seconds: float = 2.0,
    max_no_improve: int = 0,
    raw_test: bool = False,
):
    """Improve a given assignment with Algo4's small-IP release-and-repair loop."""
    inst = parse_instance(instance_file)
    if assignment is None:
        assignment, _ = pre_build(instance_file, raw_test=raw_test)
    assignment = _normalize_assignment(inst, assignment)

    deadline = time.perf_counter() + max_seconds
    rng = random.Random(seed)
    ctx = _build_context(inst)
    current_routes = _assignment_to_routes(inst, assignment)
    if sum(1 for car_id in assignment if _accepted(car_id)) == inst.n_orders:
        return _routes_to_solution(inst, ctx, current_routes)

    select_candidate_orders, solve_local_ip = _algo4_helpers()
    current_profit = _profit_from_routes(inst, current_routes)
    best_routes = {car_id: route[:] for car_id, route in current_routes.items()}
    best_profit = current_profit
    no_improve = 0

    for _ in range(iterations):
        remaining_wall = deadline - time.perf_counter()
        if remaining_wall <= 0 or (max_no_improve > 0 and no_improve >= max_no_improve):
            break

        car_ids = _sample_routes_by_softmax_efficiency(
            inst,
            ctx,
            current_routes,
            rng,
            temperature,
            batch_size,
        )
        if not car_ids:
            break

        base_routes = {cid: route[:] for cid, route in current_routes.items()}
        released_orders: set[int] = set()
        for car_id in car_ids:
            released_orders.update(base_routes[car_id])
            base_routes[car_id] = []

        used_without_car = _moving_from_routes(inst, ctx, base_routes)
        remaining_budget = inst.moving_budget - used_without_car
        if remaining_budget < 0:
            continue

        assigned_elsewhere = {
            order_id
            for cid, route in base_routes.items()
            if cid not in car_ids
            for order_id in route
        }
        available = {order.id for order in inst.orders if order.id not in assigned_elsewhere}
        candidates = select_candidate_orders(
            inst.orders,
            ctx,
            car_ids,
            available,
            released_orders,
            candidate_order_limit,
        )
        if not candidates:
            continue

        if deadline - time.perf_counter() <= 0.05:
            break
        repaired = None
        limit = len(candidates)
        attempts = 0
        while repaired is None and limit >= 12 and attempts < 4:
            repaired = solve_local_ip(
                inst,
                ctx,
                car_ids,
                candidates[:limit],
                remaining_budget,
                per_ip_seconds,
                deadline,
            )
            limit //= 2
            attempts += 1
        if repaired is None:
            no_improve += 1
            continue

        trial_routes = {cid: route[:] for cid, route in base_routes.items()}
        trial_routes.update(repaired)
        moving = _moving_from_routes(inst, ctx, trial_routes)
        if moving > inst.moving_budget:
            no_improve += 1
            continue

        profit = _profit_from_routes(inst, trial_routes)
        if profit <= current_profit:
            no_improve += 1
            continue

        current_routes = trial_routes
        current_profit = profit
        no_improve = 0
        if current_profit > best_profit:
            best_routes = {car_id: route[:] for car_id, route in current_routes.items()}
            best_profit = current_profit

    return _routes_to_solution(inst, ctx, best_routes)


def heuristic_algorithm(
    instance_file: str | Path = "data/instance05.txt",
    *args: Any,
    iterations: int = 100000,
    max_seconds: float = 170.0,
    seed: int = 1142,
    temperature: float = 0.35,
    batch_size: int = 5,
    candidate_order_limit: int = 160,
    per_ip_seconds: float = 2.0,
    max_no_improve: int = 0,
    raw_test: bool = False,
    **kwargs: Any,
):
    """Algo1/Algo5 union pre-build followed by Algo4-style small-IP improve."""
    start = time.perf_counter()
    assignment, relocation = pre_build(instance_file, raw_test=raw_test)
    remaining_seconds = max_seconds - (time.perf_counter() - start)
    if remaining_seconds <= 0.05:
        result = (assignment, relocation)
    else:
        try:
            result = small_ip_improve(
                instance_file,
                assignment,
                iterations=iterations,
                max_seconds=remaining_seconds,
                seed=seed,
                temperature=temperature,
                batch_size=batch_size,
                candidate_order_limit=candidate_order_limit,
                per_ip_seconds=per_ip_seconds,
                max_no_improve=max_no_improve,
                raw_test=raw_test,
            )
        except Exception:
            # The improvement phase depends on the small local IP helper. If
            # Gurobi or its license is unavailable in the grading environment,
            # keep the strong deterministic pre-build solution instead of
            # failing the whole submission.
            result = (assignment, relocation)
    if raw_test:
        return result
    return _to_grading_output(*result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--max-seconds", type=float, default=170.0)
    parser.add_argument("--seed", type=int, default=1142)
    parser.add_argument("--temperature", type=float, default=0.35)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--candidate-order-limit", type=int, default=160)
    parser.add_argument("--per-ip-seconds", type=float, default=2.0)
    parser.add_argument(
        "--max-no-improve",
        type=int,
        default=0,
        help="stop after this many non-improving repairs; 0 disables this guard",
    )
    parser.add_argument("--raw-test", action="store_true")
    args = parser.parse_args()

    inst = parse_instance(args.instance)
    start = time.perf_counter()
    pre_assignment, pre_relocation, meta = pre_build(args.instance, raw_test=args.raw_test, return_metadata=True)
    remaining_seconds = args.max_seconds - (time.perf_counter() - start)
    if remaining_seconds <= 0.05:
        assignment, relocation = pre_assignment, pre_relocation
    else:
        assignment, relocation = small_ip_improve(
            args.instance,
            pre_assignment,
            iterations=args.iterations,
            max_seconds=remaining_seconds,
            seed=args.seed,
            temperature=args.temperature,
            batch_size=args.batch_size,
            candidate_order_limit=args.candidate_order_limit,
            per_ip_seconds=args.per_ip_seconds,
            max_no_improve=args.max_no_improve,
            raw_test=args.raw_test,
        )
    final_profit = _profit_from_assignment(inst, assignment)
    accepted = [order for order in inst.orders if assignment[order.id - 1]]
    print(f"pre_build_source = {meta['source']}")
    print(f"pre_build_profit = {meta['profit']}")
    print(f"pre_build_candidates = {meta['candidates']}")
    print(f"accepted_orders = {len(accepted)} / {inst.n_orders}")
    print(f"profit = {final_profit}")
    print(f"moving_time = {sum(row[5] for row in relocation)} / {inst.moving_budget}")


if __name__ == "__main__":
    main()
