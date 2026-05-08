from __future__ import annotations

import argparse
import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mtp_common import (
    Order,
    can_serve_level,
    format_minute,
    order_ready_minute,
    parse_instance,
)


LAMBDA_SET = [0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8]
TOP_K_STATIONS = 5


@dataclass(frozen=True)
class PathPlan:
    car_id: int
    order_ids: list[int]
    move_time: int
    weight: float


@dataclass(frozen=True)
class Candidate:
    car_id: int
    station: int
    ready: int
    move_time: int
    weight: float
    sales: int
    route: tuple[int, ...]


@dataclass(frozen=True)
class Algo2Context:
    total_revenue: int
    revenue_weight: dict[int, float]
    budget_scale: int
    move_matrix: list[list[int]]
    nearest_sources: dict[int, list[int]]
    compatible_by_level_time: dict[int, list[Order]]


def heuristic_algorithm2(
    instance_file: str | Path = "data/instance05.txt",
    lambdas: Iterable[float] = LAMBDA_SET,
    seed: int = 1142,
    max_seconds: float = 165.0,
    raw_test: bool = False,
):
    """Greedy trajectory heuristic.

    For each level, solve one sweep-DP trajectory over active compatible orders.
    The arc weight is `3R/sum_R - lambda * moving_time/(1+B)`.
    Once a car takes a trajectory, those orders are removed for later cars.
    """
    inst = parse_instance(instance_file)
    ctx = _build_context(inst)
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

    level_orders = [
        sorted(range(1, inst.n_levels + 1), reverse=True),
        sorted(range(1, inst.n_levels + 1), key=lambda level: -inst.rates[level]),
    ]
    for lam in lambdas:
        for levels in level_orders:
            assignment, relocations = _run_level_order(inst, ctx, levels, lam)
            profit = _profit(inst, assignment)
            moving = sum(row[5] for row in relocations)
            if moving <= inst.moving_budget and profit > best_profit:
                best_profit = profit
                best_assignment = assignment
                best_relocations = relocations

    if best_assignment is None or best_relocations is None:
        return [0] * inst.n_orders, []
    return best_assignment, best_relocations


def _run_level_order(inst, ctx: Algo2Context, levels: list[int], lam: float) -> tuple[list[int], list[list]]:
    available = {order.id for order in inst.orders}
    routes: dict[int, list[int]] = {car.id: [] for car in inst.cars}
    cars_by_level = {level: [] for level in range(1, inst.n_levels + 1)}
    for car in inst.cars:
        cars_by_level[car.level].append(car)
    for level_cars in cars_by_level.values():
        level_cars.sort(key=lambda car: car.id)

    used_budget = 0
    candidate_levels = [level for level in levels if cars_by_level[level]]
    idx = 0
    while idx < len(candidate_levels):
        level = candidate_levels[idx]
        idx += 1
        level_cars = cars_by_level[level]
        if not level_cars:
            continue
        remaining_budget = inst.moving_budget - used_budget
        if remaining_budget < 0:
            break
        plan = _best_path_for_level(inst, ctx, level, level_cars, available, remaining_budget, lam)
        if plan is None or not plan.order_ids:
            continue
        routes[plan.car_id] = plan.order_ids
        used_budget += plan.move_time
        available.difference_update(plan.order_ids)
        cars_by_level[level] = [car for car in level_cars if car.id != plan.car_id]
        if cars_by_level[level]:
            candidate_levels.append(level)
    return _routes_to_solution(inst, routes)


def _build_context(inst) -> Algo2Context:
    total_revenue = max(1, sum(order.revenue for order in inst.orders))
    revenue_weight = {order.id: 3 * order.revenue / total_revenue for order in inst.orders}
    move_matrix = [[0] * (inst.n_stations + 1) for _ in range(inst.n_stations + 1)]
    for (src, dst), minutes in inst.move_time.items():
        move_matrix[src][dst] = minutes
    nearest_sources = {
        dst: sorted(
            range(1, inst.n_stations + 1),
            key=lambda src: (move_matrix[src][dst], src),
        )[:TOP_K_STATIONS]
        for dst in range(1, inst.n_stations + 1)
    }

    compatible_by_level_time: dict[int, list[Order]] = {}
    for level in range(1, inst.n_levels + 1):
        compatible = [order for order in inst.orders if can_serve_level(level, order.level)]
        compatible_by_level_time[level] = sorted(
            compatible,
            key=lambda order: (order.pickup_minute, -order.revenue, order.id),
        )

    return Algo2Context(
        total_revenue=total_revenue,
        revenue_weight=revenue_weight,
        budget_scale=1 + inst.moving_budget,
        move_matrix=move_matrix,
        nearest_sources=nearest_sources,
        compatible_by_level_time=compatible_by_level_time,
    )


def _best_path_for_level(
    inst,
    ctx: Algo2Context,
    level: int,
    cars,
    available: set[int],
    remaining_budget: int,
    lam: float,
) -> PathPlan | None:
    orders = [order for order in ctx.compatible_by_level_time[level] if order.id in available]
    if not orders:
        return None

    move_matrix = ctx.move_matrix
    revenue_weight = ctx.revenue_weight
    move_penalty = lam / ctx.budget_scale
    initials = [Candidate(car.id, car.station, 0, 0, 0.0, 0, ()) for car in cars]
    val: list[Candidate | None] = [None] * (inst.n_stations + 1)
    release_heap: list[tuple[int, int, Candidate]] = []
    for seq, initial in enumerate(initials):
        current = val[initial.station]
        if current is None or _candidate_key(initial) > _candidate_key(current):
            val[initial.station] = initial
        heapq.heappush(release_heap, (0, seq, initial))
    all_candidates: list[Candidate] = []
    seq = len(initials)

    for order in orders:
        cutoff = order.pickup_minute - 30
        while release_heap and release_heap[0][0] <= cutoff:
            _, _, candidate = heapq.heappop(release_heap)
            current = val[candidate.station]
            if current is None or _candidate_key(candidate) > _candidate_key(current):
                val[candidate.station] = candidate

        best_parent = None
        best_key = None
        pickup_station = order.pickup_station
        for station in ctx.nearest_sources[pickup_station]:
            candidate = val[station]
            if candidate is None:
                continue
            move = move_matrix[station][pickup_station]
            total_move = candidate.move_time + move
            can_start_now = candidate.ready == 0 and move == 0 and order.pickup_minute == 0
            if total_move > remaining_budget or (
                not can_start_now and candidate.ready + move > cutoff
            ):
                continue
            sales = candidate.sales + order.revenue
            weight = candidate.weight + revenue_weight[order.id] - move_penalty * move
            key = (weight, sales, -total_move, -candidate.ready)
            if best_key is None or key > best_key:
                best_key = key
                best_parent = (candidate, total_move, weight, sales)

        if best_parent is None:
            continue
        parent, total_move, weight, sales = best_parent
        new_candidate = Candidate(
            parent.car_id,
            order.return_station,
            order_ready_minute(order),
            total_move,
            weight,
            sales,
            parent.route + (order.id,),
        )
        heapq.heappush(release_heap, (new_candidate.ready, seq, new_candidate))
        all_candidates.append(new_candidate)
        seq += 1

    best_candidate = None
    best_key = None
    for candidate in all_candidates:
        if candidate.move_time > remaining_budget:
            continue
        key = _candidate_key(candidate)
        if best_key is None or key > best_key:
            best_key = key
            best_candidate = candidate

    if best_candidate is None:
        return None
    return PathPlan(best_candidate.car_id, list(best_candidate.route), best_candidate.move_time, best_candidate.weight)


def _candidate_key(candidate: Candidate) -> tuple[float, int, int]:
    return candidate.weight, candidate.sales, -candidate.move_time


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
    parser.add_argument("--lambdas", default="0", help="ignored; kept for compatibility")
    parser.add_argument("--max-seconds", type=float, default=165.0, help="ignored in this greedy version")
    parser.add_argument("--raw-test", action="store_true")
    args = parser.parse_args()
    inst = parse_instance(args.instance)
    assignment, relocation = heuristic_algorithm2(args.instance, raw_test=args.raw_test)
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
