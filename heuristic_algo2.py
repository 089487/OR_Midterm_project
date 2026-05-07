from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mtp_common import (
    Order,
    can_serve_level,
    feasible_transition,
    format_minute,
    order_ready_minute,
    parse_instance,
)


LAMBDA_SET = [0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8]


@dataclass(frozen=True)
class PathPlan:
    car_id: int
    order_ids: list[int]
    move_time: int
    weight: float


def heuristic_algorithm2(
    instance_file: str | Path = "data/instance05.txt",
    lambdas: Iterable[float] = LAMBDA_SET,
    seed: int = 1142,
    max_seconds: float = 165.0,
    raw_test: bool = False,
):
    """Batch longest-path heuristic.

    Each car gets a maximum-weight feasible route over currently unassigned orders.
    The normalized arc prize for appending order j after i is
    `3R_j / sum_R - lambda * t_ij / (1 + B)`.
    After a car route is selected, those orders are masked out for all later cars.
    """
    inst = parse_instance(instance_file)
    deadline = time.perf_counter() + max_seconds
    best_assignment: list[int] | None = None
    best_relocations: list[list] | None = None
    best_profit = -10**30

    if not raw_test:
        try:
            from algorithm_module import heuristic_algorithm

            baseline_assignment, baseline_relocations = heuristic_algorithm(instance_file, raw_test=False)
            best_assignment = baseline_assignment
            best_relocations = baseline_relocations
            best_profit = _profit(inst, baseline_assignment)
        except Exception:
            pass

    parity_orders = [(0, 1), (1, 0)]
    rng = random.Random(seed)
    shuffled = parity_orders[:]
    rng.shuffle(shuffled)
    parity_orders.extend(shuffled)

    lambdas = list(lambdas)
    if inst.n_orders > 1500:
        car_order_modes = ("early",)
    else:
        car_order_modes = ("early", "level_desc", "random")

    stop = False
    for lam in lambdas:
        if stop or time.perf_counter() >= deadline:
            break
        for parity_order in parity_orders:
            if stop or time.perf_counter() >= deadline:
                break
            for car_order_mode in car_order_modes:
                if time.perf_counter() >= deadline:
                    stop = True
                    break
                available = {order.id for order in inst.orders}
                routes: dict[int, list[int]] = {car.id: [] for car in inst.cars}
                used_budget = 0

                for parity in parity_order:
                    if time.perf_counter() >= deadline:
                        stop = True
                        break
                    cars = [car for car in inst.cars if car.level % 2 == parity]
                    if car_order_mode == "early":
                        cars.sort(key=lambda car: (car.level, car.id))
                    elif car_order_mode == "level_desc":
                        cars.sort(key=lambda car: (-car.level, car.id))
                    else:
                        rng.shuffle(cars)

                    for car in cars:
                        if time.perf_counter() >= deadline:
                            stop = True
                            break
                        remaining_budget = inst.moving_budget - used_budget
                        if remaining_budget < 0:
                            break
                        plan = _best_path_for_car(inst, car, available, lam, remaining_budget)
                        if plan is None or not plan.order_ids:
                            continue
                        routes[car.id] = plan.order_ids
                        used_budget += plan.move_time
                        available.difference_update(plan.order_ids)

                assignment, relocations = _routes_to_solution(inst, routes)
                profit = _profit(inst, assignment)
                moving = sum(row[5] for row in relocations)
                if moving <= inst.moving_budget and profit > best_profit:
                    best_profit = profit
                    best_assignment = assignment
                    best_relocations = relocations

    if best_assignment is None or best_relocations is None:
        return [0] * inst.n_orders, []
    return best_assignment, best_relocations


def _best_path_for_car(inst, car, available: set[int], lam: float, remaining_budget: int) -> PathPlan | None:
    all_orders = [order for order in inst.orders if order.id in available and can_serve_level(car.level, order.level)]
    if not all_orders:
        return None

    total_revenue = max(1, sum(order.revenue for order in inst.orders))
    budget_scale = 1 + inst.moving_budget
    orders = _candidate_orders(all_orders, inst.n_orders)
    orders.sort(key=lambda order: (order.pickup_minute, -order.revenue, order.id))
    n = len(orders)
    dp = [-10**30] * n
    move_sum = [0] * n
    prev_idx = [-1] * n

    max_prev_scan = 260 if inst.n_orders <= 1500 else 35
    for j, order in enumerate(orders):
        ok, move, _ = feasible_transition(inst, None, car.station, order)
        if ok and move <= remaining_budget:
            dp[j] = _arc_weight(order.revenue, move, total_revenue, budget_scale, lam)
            move_sum[j] = move

        scanned = 0
        i = j - 1
        while i >= 0 and scanned < max_prev_scan:
            prev = orders[i]
            if order.pickup_minute - prev.pickup_minute > 14 * 24 * 60 and inst.n_orders > 1500:
                break
            ok, move, _ = feasible_transition(inst, prev, prev.return_station, order)
            total_move = move_sum[i] + move
            if ok and dp[i] > 0 and total_move <= remaining_budget:
                value = dp[i] + _arc_weight(order.revenue, move, total_revenue, budget_scale, lam)
                if value > dp[j]:
                    dp[j] = value
                    move_sum[j] = total_move
                    prev_idx[j] = i
            scanned += 1
            i -= 1

    best_end = -1
    best_key = None
    for idx, value in enumerate(dp):
        if value <= 0 or move_sum[idx] > remaining_budget:
            continue
        sales = _path_sales(orders, prev_idx, idx)
        key = (value, sales, -move_sum[idx])
        if best_key is None or key > best_key:
            best_key = key
            best_end = idx

    if best_end < 0:
        return None

    chosen: list[int] = []
    cur = best_end
    while cur >= 0:
        chosen.append(orders[cur].id)
        cur = prev_idx[cur]
    chosen.reverse()
    return PathPlan(car.id, chosen, move_sum[best_end], dp[best_end])


def _arc_weight(revenue: int, move: int, total_revenue: int, budget_scale: int, lam: float) -> float:
    return 3 * revenue / total_revenue - lam * move / budget_scale


def _candidate_orders(orders: list[Order], n_orders: int) -> list[Order]:
    if n_orders <= 1500 or len(orders) <= 900:
        return orders
    by_revenue = sorted(orders, key=lambda order: (-order.revenue, order.pickup_minute, order.id))[:260]
    return by_revenue


def _path_sales(orders: list[Order], prev_idx: list[int], end_idx: int) -> int:
    total = 0
    cur = end_idx
    while cur >= 0:
        total += orders[cur].revenue
        cur = prev_idx[cur]
    return total


def _routes_to_solution(inst, routes: dict[int, list[int]]) -> tuple[list[int], list[list]]:
    assignment = [0] * inst.n_orders
    relocations: list[list] = []
    order_by_id = {order.id: order for order in inst.orders}
    car_by_id = {car.id: car for car in inst.cars}

    for car_id, route in routes.items():
        car = car_by_id[car_id]
        station = car.station
        ready = 0
        for order_id in route:
            order = order_by_id[order_id]
            assignment[order.id - 1] = car_id
            move = inst.move_time[(station, order.pickup_station)]
            if move > 0:
                relocations.append(
                    [
                        car_id,
                        station,
                        order.pickup_station,
                        format_minute(inst, ready),
                        format_minute(inst, ready + move),
                        move,
                        f"before order {order.id}",
                    ]
                )
            station = order.return_station
            ready = order_ready_minute(order)
    return assignment, relocations


def _profit(inst, assignment: list[int]) -> int:
    accepted_sales = sum(order.revenue for order in inst.orders if assignment[order.id - 1])
    rejected_sales = sum(order.revenue for order in inst.orders if not assignment[order.id - 1])
    return accepted_sales - 2 * rejected_sales


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--seed", type=int, default=1142)
    parser.add_argument("--lambdas", default=",".join(map(str, LAMBDA_SET)))
    parser.add_argument("--max-seconds", type=float, default=165.0)
    parser.add_argument("--raw-test", action="store_true")
    args = parser.parse_args()
    lambdas = [float(x) for x in args.lambdas.split(",") if x.strip()]
    inst = parse_instance(args.instance)
    assignment, relocation = heuristic_algorithm2(
        args.instance,
        lambdas=lambdas,
        seed=args.seed,
        max_seconds=args.max_seconds,
        raw_test=args.raw_test,
    )
    accepted = [order for order in inst.orders if assignment[order.id - 1]]
    rejected = [order for order in inst.orders if not assignment[order.id - 1]]
    sales = sum(order.revenue for order in accepted)
    profit = sales - 2 * sum(order.revenue for order in rejected)
    print(f"accepted_orders = {len(accepted)} / {inst.n_orders}")
    print(f"accepted_sales = {sales}")
    print(f"profit = {profit}")
    print(f"moving_time = {sum(row[5] for row in relocation)} / {inst.moving_budget}")


if __name__ == "__main__":
    main()
