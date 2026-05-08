from __future__ import annotations

import argparse
import heapq
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from algorithm_module import heuristic_algorithm
from mtp_common import (
    Order,
    can_serve_level,
    format_minute,
    latest_arrival_for_pickup,
    order_ready_minute,
    parse_instance,
)


LAMBDA_SET = [0, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0]
TOP_K_STATIONS = 10


@dataclass(frozen=True)
class Candidate:
    station: int
    ready: int
    move_time: int
    weight: float
    sales: int
    route: tuple[int, ...]


@dataclass(frozen=True)
class Plan:
    order_ids: list[int]
    move_time: int
    sales: int
    weight: float


@dataclass(frozen=True)
class Algo3Context:
    total_revenue: int
    revenue_weight: dict[int, float]
    move_matrix: list[list[int]]
    nearest_sources: dict[int, list[int]]
    order_by_id: dict[int, Order]
    car_by_id: dict[int, object]


def heuristic_algorithm3(
    instance_file: str | Path = "data/instance05.txt",
    lambdas: Iterable[float] = LAMBDA_SET,
    iterations: int = 100000,
    max_seconds: float = 100.0,
    raw_test: bool = False,
):
    """Algo1 plus release-one-car local search.

    Start from Algo1, then repeatedly pick the rejected-order level with the
    largest total revenue. For that level, release the weakest compatible car
    route and rebuild only that single car with a sweep DP using top-10 station
    transfers.
    """
    inst = parse_instance(instance_file)
    deadline = time.perf_counter() + max_seconds
    lambdas = list(lambdas)
    assignment, _ = heuristic_algorithm(instance_file, raw_test=raw_test)
    ctx = _build_context(inst)
    routes = _assignment_to_routes(inst, assignment)
    best_routes = {car_id: route[:] for car_id, route in routes.items()}
    best_profit = _profit_from_routes(inst, best_routes)
    blocked_levels: set[int] = set()

    for _ in range(iterations):
        if time.perf_counter() >= deadline:
            break
        target_level = _highest_rejected_level(inst, best_routes, blocked_levels)
        if target_level is None:
            break
        car_id = _weakest_car_for_level(inst, best_routes, target_level)
        if car_id is None:
            blocked_levels.add(target_level)
            continue
        old_route = best_routes[car_id][:]
        if not old_route:
            blocked_levels.add(target_level)
            continue

        base_routes = {cid: route[:] for cid, route in best_routes.items()}
        released_orders = set(base_routes[car_id])
        base_routes[car_id] = []
        used_without_car = _moving_from_routes(inst, ctx, base_routes)
        remaining_budget = inst.moving_budget - used_without_car
        if remaining_budget < 0:
            blocked_levels.add(target_level)
            continue

        assigned_elsewhere = {
            order_id
            for cid, route in base_routes.items()
            if cid != car_id
            for order_id in route
        }
        available = {order.id for order in inst.orders if order.id not in assigned_elsewhere}
        available.update(released_orders)

        best_iteration_routes = None
        best_iteration_profit = best_profit
        car = ctx.car_by_id[car_id]
        budget_scale = 1 + max(0, remaining_budget)
        for lam in lambdas:
            if time.perf_counter() >= deadline:
                break
            plan = _best_path_for_car_topk(inst, ctx, car, available, remaining_budget, budget_scale, lam)
            trial_routes = {cid: route[:] for cid, route in base_routes.items()}
            trial_routes[car_id] = [] if plan is None else plan.order_ids
            if trial_routes[car_id] == old_route:
                continue
            moving = _moving_from_routes(inst, ctx, trial_routes)
            if moving > inst.moving_budget:
                continue
            profit = _profit_from_routes(inst, trial_routes)
            if profit > best_iteration_profit:
                best_iteration_profit = profit
                best_iteration_routes = trial_routes

        if best_iteration_routes is None:
            blocked_levels.add(target_level)
            continue
        best_routes = best_iteration_routes
        best_profit = best_iteration_profit
        blocked_levels.clear()

    return _routes_to_solution(inst, ctx, best_routes)


def _build_context(inst) -> Algo3Context:
    total_revenue = max(1, sum(order.revenue for order in inst.orders))
    revenue_weight = {order.id: 3 * order.revenue / total_revenue for order in inst.orders}
    move_matrix = [[0] * (inst.n_stations + 1) for _ in range(inst.n_stations + 1)]
    for (src, dst), minutes in inst.move_time.items():
        move_matrix[src][dst] = minutes
    nearest_sources = {
        dst: sorted(range(1, inst.n_stations + 1), key=lambda src: (move_matrix[src][dst], src))[
            :TOP_K_STATIONS
        ]
        for dst in range(1, inst.n_stations + 1)
    }
    return Algo3Context(
        total_revenue=total_revenue,
        revenue_weight=revenue_weight,
        move_matrix=move_matrix,
        nearest_sources=nearest_sources,
        order_by_id={order.id: order for order in inst.orders},
        car_by_id={car.id: car for car in inst.cars},
    )


def _assignment_to_routes(inst, assignment: list[int]) -> dict[int, list[int]]:
    routes = {car.id: [] for car in inst.cars}
    order_by_id = {order.id: order for order in inst.orders}
    for order_id, car_id in enumerate(assignment, start=1):
        if car_id:
            routes[car_id].append(order_id)
    for route in routes.values():
        route.sort(key=lambda order_id: (order_by_id[order_id].pickup_minute, order_id))
    return routes


def _highest_rejected_level(inst, routes: dict[int, list[int]], blocked_levels: set[int]) -> int | None:
    accepted = {order_id for route in routes.values() for order_id in route}
    revenue_by_level: dict[int, int] = {}
    for order in inst.orders:
        if order.id not in accepted and order.level not in blocked_levels:
            revenue_by_level[order.level] = revenue_by_level.get(order.level, 0) + order.revenue
    if not revenue_by_level:
        return None
    return max(revenue_by_level, key=lambda level: (revenue_by_level[level], level))


def _weakest_car_for_level(inst, routes: dict[int, list[int]], level: int) -> int | None:
    order_by_id = {order.id: order for order in inst.orders}
    candidates = []
    for car in inst.cars:
        if not can_serve_level(car.level, level):
            continue
        route_sales = sum(order_by_id[order_id].revenue for order_id in routes[car.id])
        route_len = len(routes[car.id])
        exact_bonus = 0 if car.level == level else 1
        candidates.append((route_sales, route_len, exact_bonus, car.id))
    if not candidates:
        return None
    return min(candidates)[-1]


def _best_path_for_car_topk(
    inst,
    ctx: Algo3Context,
    car,
    available: set[int],
    remaining_budget: int,
    budget_scale: int,
    lam: float,
) -> Plan | None:
    orders = [
        order
        for order in inst.orders
        if order.id in available and can_serve_level(car.level, order.level)
    ]
    orders.sort(key=lambda order: (order.pickup_minute, -order.revenue, order.id))
    if not orders:
        return None

    move_penalty = lam / max(1, budget_scale)
    initial = Candidate(car.station, 0, 0, 0.0, 0, ())
    val: list[Candidate | None] = [None] * (inst.n_stations + 1)
    release_heap: list[tuple[int, int, Candidate]] = [(0, 0, initial)]
    all_candidates: list[Candidate] = []
    seq = 1

    for order in orders:
        cutoff = latest_arrival_for_pickup(order)
        while release_heap and release_heap[0][0] <= cutoff:
            _, _, candidate = heapq.heappop(release_heap)
            current = val[candidate.station]
            if current is None or _candidate_key(candidate) > _candidate_key(current):
                val[candidate.station] = candidate

        best_parent = None
        best_key = None
        for station in ctx.nearest_sources[order.pickup_station]:
            candidate = val[station]
            if candidate is None:
                continue
            move = ctx.move_matrix[station][order.pickup_station]
            total_move = candidate.move_time + move
            can_start_now = candidate.ready == 0 and move == 0 and order.pickup_minute == 0
            if total_move > remaining_budget or (
                not can_start_now and candidate.ready + move > cutoff
            ):
                continue
            sales = candidate.sales + order.revenue
            weight = candidate.weight + ctx.revenue_weight[order.id] - move_penalty * move
            key = (weight, sales, -total_move, -candidate.ready)
            if best_key is None or key > best_key:
                best_key = key
                best_parent = (candidate, total_move, weight, sales)

        if best_parent is None:
            continue
        parent, total_move, weight, sales = best_parent
        new_candidate = Candidate(
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

    if not all_candidates:
        return None
    best = max(all_candidates, key=_candidate_key)
    return Plan(list(best.route), best.move_time, best.sales, best.weight)


def _candidate_key(candidate: Candidate) -> tuple[float, int, int]:
    return candidate.weight, candidate.sales, -candidate.move_time


def _moving_from_routes(inst, ctx: Algo3Context, routes: dict[int, list[int]]) -> int:
    total = 0
    for car_id, route in routes.items():
        station = ctx.car_by_id[car_id].station
        for order_id in route:
            order = ctx.order_by_id[order_id]
            total += ctx.move_matrix[station][order.pickup_station]
            station = order.return_station
    return total


def _profit_from_routes(inst, routes: dict[int, list[int]]) -> int:
    accepted = {order_id for route in routes.values() for order_id in route}
    accepted_sales = sum(order.revenue for order in inst.orders if order.id in accepted)
    rejected_sales = sum(order.revenue for order in inst.orders if order.id not in accepted)
    return accepted_sales - 2 * rejected_sales


def _routes_to_solution(inst, ctx: Algo3Context, routes: dict[int, list[int]]) -> tuple[list[int], list[list]]:
    assignment = [0] * inst.n_orders
    relocations: list[list] = []
    for car_id, route in routes.items():
        car = ctx.car_by_id[car_id]
        station = car.station
        ready = 0
        for order_id in route:
            order = ctx.order_by_id[order_id]
            assignment[order.id - 1] = car_id
            move = ctx.move_matrix[station][order.pickup_station]
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--lambdas", default=",".join(map(str, LAMBDA_SET)))
    parser.add_argument("--max-seconds", type=float, default=100.0)
    parser.add_argument("--raw-test", action="store_true")
    args = parser.parse_args()
    lambdas = [float(x) for x in args.lambdas.split(",") if x.strip()]
    inst = parse_instance(args.instance)
    assignment, relocation = heuristic_algorithm3(
        args.instance,
        lambdas=lambdas,
        iterations=args.iterations,
        max_seconds=args.max_seconds,
        raw_test=args.raw_test,
    )
    accepted = [order for order in inst.orders if assignment[order.id - 1]]
    rejected = [order for order in inst.orders if not assignment[order.id - 1]]
    sales = sum(order.revenue for order in accepted)
    print(f"accepted_orders = {len(accepted)} / {inst.n_orders}")
    print(f"accepted_sales = {sales}")
    print(f"profit = {sales - 2 * sum(order.revenue for order in rejected)}")
    print(f"moving_time = {sum(row[5] for row in relocation)} / {inst.moving_budget}")


if __name__ == "__main__":
    main()
