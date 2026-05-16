from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mtp_common import (
    Order,
    can_serve_level,
    format_minute,
    latest_arrival_for_pickup,
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
    """Chronological lower-bound heuristic.

    Orders are processed by pick-up time. Each accepted order is assigned to the
    feasible car with the smallest immediate moving time. Rejected orders remain
    0 in the assignment list.
    """
    inst = parse_instance(instance_file)
    states = {
        car.id: CarState(car.id, car.level, car.station)
        for car in inst.cars
    }
    order_by_id = {order.id: order for order in inst.orders}
    assignment = [0] * inst.n_orders
    used_budget = 0

    for order in sorted(inst.orders, key=lambda o: (o.pickup_minute, o.id)):
        candidate = _choose_min_move_car(inst, states.values(), order, inst.moving_budget - used_budget)
        if candidate is None:
            continue
        state, move = candidate
        used_budget += move
        assignment[order.id - 1] = state.car_id
        state.route.append(order.id)
        state.station = order.return_station
        state.ready = order_ready_minute(order)

    return assignment, _build_relocations(inst, states.values(), order_by_id)


def _choose_min_move_car(inst, states, order: Order, remaining_budget: int) -> tuple[CarState, int] | None:
    best: tuple[tuple[int, int, int, int], CarState, int] | None = None
    cutoff = latest_arrival_for_pickup(order)
    for state in states:
        if not can_serve_level(state.level, order.level):
            continue
        move = inst.move_time[(state.station, order.pickup_station)]
        if move > remaining_budget:
            continue
        starts_at_horizon_same_station = state.ready == 0 and move == 0 and order.pickup_minute == 0
        if not starts_at_horizon_same_station and state.ready + move > cutoff:
            continue
        idle = max(0, cutoff - (state.ready + move))
        upgrade_penalty = state.level - order.level
        key = (move, upgrade_penalty, idle, state.car_id)
        if best is None or key < best[0]:
            best = (key, state, move)
    if best is None:
        return None
    return best[1], best[2]


def _build_relocations(inst, states, order_by_id: dict[int, Order]) -> list[list]:
    relocations: list[list] = []
    car_by_id = {car.id: car for car in inst.cars}
    for state in states:
        station = car_by_id[state.car_id].station
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


def _profit(inst, assignment: list[int]) -> int:
    accepted_revenue = sum(order.revenue for order, car_id in zip(inst.orders, assignment) if car_id)
    total_revenue = sum(order.revenue for order in inst.orders)
    return accepted_revenue - 2 * (total_revenue - accepted_revenue)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", nargs="?", default="data/instance05.txt")
    parser.add_argument("--full", action="store_true", help="print full assignment and relocation lists")
    parser.add_argument("--raw-test", action="store_true", help="accepted for benchmark API compatibility")
    args = parser.parse_args()

    inst = parse_instance(args.instance)
    assignment, relocation = heuristic_algorithm(args.instance, raw_test=args.raw_test)
    print(f"accepted_orders = {sum(1 for car_id in assignment if car_id)} / {len(assignment)}")
    print(f"profit = {_profit(inst, assignment)}")
    print(f"relocations = {len(relocation)}")
    print(f"moving_time = {sum(row[5] for row in relocation)} / {inst.moving_budget}")
    if args.full:
        print("assignment =", assignment)
        print("relocation =")
        for row in relocation:
            print(row)


if __name__ == "__main__":
    main()
