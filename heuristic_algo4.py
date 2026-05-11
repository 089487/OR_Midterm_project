from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Iterable

import gurobipy as gp
from gurobipy import GRB

from algorithm_module import heuristic_algorithm
from heuristic_algo3 import (
    _assignment_to_routes,
    _build_context,
    _moving_from_routes,
    _profit_from_routes,
    _routes_to_solution,
    _sample_routes_by_softmax_efficiency,
)
from mtp_common import (
    Order,
    can_serve_level,
    feasible_transition,
    parse_instance,
)


def heuristic_algorithm4(
    instance_file: str | Path = "data/instance05.txt",
    lambdas: Iterable[float] | None = None,
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
    """Algo1 plus local IP repair.

    This follows Algo3's release-and-repair loop, but the repair step solves a
    small IP over the released cars and a capped set of available orders.
    """
    inst = parse_instance(instance_file)
    deadline = time.perf_counter() + max_seconds
    rng = random.Random(seed)
    assignment, _ = heuristic_algorithm(instance_file, raw_test=raw_test)
    ctx = _build_context(inst)
    current_routes = _assignment_to_routes(inst, assignment)
    if sum(1 for car_id in assignment if car_id) == inst.n_orders:
        return _routes_to_solution(inst, ctx, current_routes)
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
        candidates = _select_candidate_orders(
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
            repaired = _solve_local_ip(
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


def _select_candidate_orders(
    orders: list[Order],
    ctx,
    car_ids: list[int],
    available: set[int],
    released_orders: set[int],
    limit: int,
) -> list[Order]:
    car_levels = [ctx.car_by_id[car_id].level for car_id in car_ids]
    candidates = [
        order
        for order in orders
        if order.id in available
        and any(can_serve_level(car_level, order.level) for car_level in car_levels)
    ]
    candidates.sort(
        key=lambda order: (
            order.id not in released_orders,
            -order.revenue,
            order.pickup_minute,
            order.id,
        )
    )
    return candidates[:limit]


def _solve_local_ip(
    inst,
    ctx,
    car_ids: list[int],
    orders: list[Order],
    remaining_budget: int,
    per_ip_seconds: float,
    deadline: float,
) -> dict[int, list[int]] | None:
    def out_of_time() -> bool:
        return time.perf_counter() >= deadline - 0.02

    car_arcs: list[tuple[int, int, int]] = []
    order_arcs: list[tuple[int, int, int, int]] = []

    for car_id in car_ids:
        if out_of_time():
            return None
        car = ctx.car_by_id[car_id]
        for order in orders:
            if not can_serve_level(car.level, order.level):
                continue
            ok, move, _ = feasible_transition(inst, None, car.station, order)
            if ok:
                car_arcs.append((car_id, order.id, move))

    for car_id in car_ids:
        if out_of_time():
            return None
        car = ctx.car_by_id[car_id]
        compatible = [order for order in orders if can_serve_level(car.level, order.level)]
        for prev in compatible:
            if out_of_time():
                return None
            for nxt in compatible:
                if prev.id == nxt.id:
                    continue
                ok, move, _ = feasible_transition(inst, prev, prev.return_station, nxt)
                if ok:
                    order_arcs.append((car_id, prev.id, nxt.id, move))

    order_by_id = {order.id: order for order in orders}
    model = gp.Model("algo4_local_repair")
    model.Params.OutputFlag = 0
    remaining_seconds = deadline - time.perf_counter()
    if remaining_seconds <= 0.05:
        return None
    model.Params.TimeLimit = max(0.05, min(per_ip_seconds, remaining_seconds))
    model.Params.MIPFocus = 1

    start = model.addVars([(c, k) for c, k, _ in car_arcs], vtype=GRB.BINARY, name="start")
    link = model.addVars([(c, i, j) for c, i, j, _ in order_arcs], vtype=GRB.BINARY, name="link")
    y = model.addVars([order.id for order in orders], vtype=GRB.BINARY, name="accept")

    incoming_by_order = {order.id: [] for order in orders}
    for c, k, _ in car_arcs:
        incoming_by_order[k].append(start[c, k])
    for c, i, j, _ in order_arcs:
        incoming_by_order[j].append(link[c, i, j])

    for order in orders:
        model.addConstr(gp.quicksum(incoming_by_order[order.id]) == y[order.id])

    arcs_by_car: dict[int, list[tuple[int, int, int]]] = {car_id: [] for car_id in car_ids}
    incoming_by_car_order: dict[tuple[int, int], list] = {
        (car_id, order.id): [] for car_id in car_ids for order in orders
    }
    outgoing_by_car_order: dict[tuple[int, int], list] = {
        (car_id, order.id): [] for car_id in car_ids for order in orders
    }
    for c, k, _ in car_arcs:
        arcs_by_car[c].append((c, k, 0))
        incoming_by_car_order[c, k].append(start[c, k])
    for c, i, j, _ in order_arcs:
        incoming_by_car_order[c, j].append(link[c, i, j])
        outgoing_by_car_order[c, i].append(link[c, i, j])

    for car_id in car_ids:
        model.addConstr(gp.quicksum(start[c, k] for c, k, _ in car_arcs if c == car_id) <= 1)
        for order in orders:
            incoming = gp.quicksum(incoming_by_car_order[car_id, order.id])
            outgoing = gp.quicksum(outgoing_by_car_order[car_id, order.id])
            model.addConstr(outgoing <= incoming)

    model.addConstr(
        gp.quicksum(move * start[c, k] for c, k, move in car_arcs)
        + gp.quicksum(move * link[c, i, j] for c, i, j, move in order_arcs)
        <= remaining_budget
    )
    model.setObjective(gp.quicksum(order_by_id[k].revenue * y[k] for k in y.keys()), GRB.MAXIMIZE)
    try:
        model.optimize()
    except gp.GurobiError:
        model.dispose()
        return None

    if model.SolCount == 0:
        model.dispose()
        return None

    successor: dict[tuple[int, int], int] = {}
    first_by_car: dict[int, int] = {}
    for c, k, _ in car_arcs:
        if start[c, k].X > 0.5:
            first_by_car[c] = k
    for c, i, j, _ in order_arcs:
        if link[c, i, j].X > 0.5:
            successor[c, i] = j

    routes = {car_id: [] for car_id in car_ids}
    for car_id, first in first_by_car.items():
        seen: set[int] = set()
        current = first
        while current and current not in seen:
            seen.add(current)
            routes[car_id].append(current)
            current = successor.get((car_id, current), 0)
    model.dispose()
    return routes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--max-seconds", type=float, default=100.0)
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
    assignment, relocation = heuristic_algorithm4(
        args.instance,
        iterations=args.iterations,
        max_seconds=args.max_seconds,
        seed=args.seed,
        temperature=args.temperature,
        batch_size=args.batch_size,
        candidate_order_limit=args.candidate_order_limit,
        per_ip_seconds=args.per_ip_seconds,
        max_no_improve=args.max_no_improve,
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
