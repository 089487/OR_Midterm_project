from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mtp_common import (
    Order,
    can_serve_level,
    feasible_transition,
    format_minute,
    order_ready_minute,
    parse_instance,
)


@dataclass
class CarState:
    car_id: int
    level: int
    station: int
    ready: int = 0
    route: list[int] = field(default_factory=list)


def heuristic_algorithm(
    instance_file: str | Path = "data/instance05.txt",
    *args: Any,
    raw_test: bool = False,
    **kwargs: Any,
):
    """Return (assignment, relocation) for an instance file.

    assignment[k - 1] is the car ID serving order k, or 0 if rejected.
    relocation is a 2-D list of records:
    [car_id, from_station, to_station, depart_time, arrive_time, moving_minutes, reason].
    """
    inst = parse_instance(instance_file)
    if not raw_test:
        exact = _try_exact_for_small_instance(instance_file, inst)
        if exact is not None:
            return exact
    orders = sorted(inst.orders, key=lambda o: (-o.revenue, o.pickup_minute, o.id))
    states = {car.id: CarState(car.id, car.level, car.station, route=[]) for car in inst.cars}
    order_by_id = {order.id: order for order in inst.orders}
    assignment = [0] * inst.n_orders
    used_budget = 0

    for order in orders:
        candidate = _choose_insertion(inst, states.values(), order_by_id, order, inst.moving_budget - used_budget)
        if candidate is None:
            continue
        state, insert_at, delta_move = candidate
        used_budget += delta_move
        assignment[order.id - 1] = state.car_id
        state.route.insert(insert_at, order.id)

    relocations = _build_relocations(inst, states.values(), order_by_id)
    return assignment, relocations


def _try_exact_for_small_instance(instance_file: str | Path, inst):
    if inst.n_orders > 80 or inst.n_cars > 120:
        return None
    try:
        from ip_solver import solve_instance

        solution = solve_instance(instance_file, time_limit=20, verbose=False)
    except Exception:
        return None
    return solution["assignment"], solution["relocations"]


def _choose_insertion(inst, states, order_by_id: dict[int, Order], order: Order, remaining_budget: int):
    best = None
    best_key = None
    for state in states:
        if not can_serve_level(state.level, order.level):
            continue
        route_orders = [order_by_id[order_id] for order_id in state.route]
        pickup_times = [route_order.pickup_minute for route_order in route_orders]
        idx = bisect_left(pickup_times, order.pickup_minute)
        prev_order = route_orders[idx - 1] if idx > 0 else None
        next_order = route_orders[idx] if idx < len(route_orders) else None
        prev_station = state.station if prev_order is None else prev_order.return_station
        ok_prev, prev_move, _ = feasible_transition(inst, prev_order, prev_station, order)
        if not ok_prev:
            continue
        next_move = 0
        old_move = 0
        if next_order is not None:
            ok_next, next_move, _ = feasible_transition(inst, order, order.return_station, next_order)
            if not ok_next:
                continue
            old_station = state.station if prev_order is None else prev_order.return_station
            _, old_move, _ = feasible_transition(inst, prev_order, old_station, next_order)
        delta_move = prev_move + next_move - old_move
        if delta_move > remaining_budget:
            continue
        idle = _local_idle(inst, prev_order, order, next_order)
        upgrade_penalty = state.level - order.level
        key = (delta_move, upgrade_penalty, idle, state.car_id)
        if best_key is None or key < best_key:
            best_key = key
            best = (state, idx, delta_move)
    return best


def _local_idle(inst, prev_order: Order | None, order: Order, next_order: Order | None) -> int:
    idle = 0
    if prev_order is not None:
        idle += order.pickup_minute - order_ready_minute(prev_order)
    if next_order is not None:
        idle += next_order.pickup_minute - order_ready_minute(order)
    return idle


def _build_relocations(inst, states, order_by_id: dict[int, Order]) -> list[list]:
    relocations: list[list] = []
    for state in states:
        station = state.station
        ready = 0
        for order_id in state.route:
            order = order_by_id[order_id]
            move = inst.move_time[(station, order.pickup_station)]
            if move > 0:
                relocations.append(
                    [
                        state.car_id,
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
    return relocations


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--full", action="store_true", help="print full assignment and relocation lists")
    parser.add_argument("--raw-test", action="store_true", help="skip the small-instance IP fallback")
    args = parser.parse_args()
    assignment, relocation = heuristic_algorithm(args.instance, raw_test=args.raw_test)
    print(f"accepted_orders = {sum(1 for car_id in assignment if car_id)} / {len(assignment)}")
    print(f"relocations = {len(relocation)}")
    print(f"moving_time = {sum(row[5] for row in relocation)}")
    if args.full:
        print("assignment =", assignment)
        print("relocation =")
        for row in relocation:
            print(row)
