from __future__ import annotations

import argparse
import heapq
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


@dataclass(frozen=True)
class Label:
    station: int
    ready: int
    move_time: int
    weight: float
    sales: int
    route: tuple[int, ...]


class ActiveOrders:
    def __init__(self, orders: list[Order], n_levels: int):
        self.order_by_id = {order.id: order for order in orders}
        self.levels: dict[int, list[int]] = {level: [] for level in range(1, n_levels + 1)}
        self.prev: dict[int, int] = {}
        self.next: dict[int, int] = {}
        self.head: dict[int, int] = {level: 0 for level in range(1, n_levels + 1)}
        self.alive = {order.id for order in orders}

        for level, group in self.levels.items():
            ids = [
                order.id
                for order in sorted(
                    (order for order in orders if order.level == level),
                    key=lambda order: (order.pickup_minute, -order.revenue, order.id),
                )
            ]
            self.levels[level] = ids
            self.head[level] = ids[0] if ids else 0
            for idx, order_id in enumerate(ids):
                self.prev[order_id] = ids[idx - 1] if idx > 0 else 0
                self.next[order_id] = ids[idx + 1] if idx + 1 < len(ids) else 0

    def iter_levels(self, levels: Iterable[int]) -> list[Order]:
        result: list[Order] = []
        for level in levels:
            current = self.head.get(level, 0)
            while current:
                result.append(self.order_by_id[current])
                current = self.next.get(current, 0)
        result.sort(key=lambda order: (order.pickup_minute, -order.revenue, order.id))
        return result

    def remove_many(self, order_ids: Iterable[int]) -> None:
        for order_id in order_ids:
            if order_id not in self.alive:
                continue
            order = self.order_by_id[order_id]
            prev_id = self.prev.get(order_id, 0)
            next_id = self.next.get(order_id, 0)
            if prev_id:
                self.next[prev_id] = next_id
            else:
                self.head[order.level] = next_id
            if next_id:
                self.prev[next_id] = prev_id
            self.alive.remove(order_id)


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

    rng = random.Random(seed)

    lambdas = list(lambdas)
    if inst.n_orders > 1500:
        car_order_modes = ("early",)
    else:
        car_order_modes = ("early", "level_desc", "random")

    stop = False
    for lam in lambdas:
        if stop or time.perf_counter() >= deadline:
            break
        for car_order_mode in car_order_modes:
            if stop or time.perf_counter() >= deadline:
                break
            active = ActiveOrders(inst.orders, inst.n_levels)
            routes: dict[int, list[int]] = {car.id: [] for car in inst.cars}
            used_budget = 0

            for level in range(inst.n_levels, 0, -1):
                if time.perf_counter() >= deadline:
                    stop = True
                    break
                cars = [car for car in inst.cars if car.level == level]
                if car_order_mode == "early":
                    cars.sort(key=lambda car: car.id)
                elif car_order_mode == "level_desc":
                    cars.sort(key=lambda car: car.station)
                else:
                    rng.shuffle(cars)

                while cars:
                    if time.perf_counter() >= deadline:
                        stop = True
                        break
                    remaining_budget = inst.moving_budget - used_budget
                    if remaining_budget < 0:
                        break
                    best_car_idx = -1
                    best_plan = None
                    for idx, car in enumerate(cars):
                        plan = _best_path_for_car(inst, car, active, lam, remaining_budget)
                        if plan is None or not plan.order_ids:
                            continue
                        if best_plan is None or (plan.weight, len(plan.order_ids), -plan.move_time) > (
                            best_plan.weight,
                            len(best_plan.order_ids),
                            -best_plan.move_time,
                        ):
                            best_plan = plan
                            best_car_idx = idx
                    if best_plan is None:
                        break
                    plan = best_plan
                    cars.pop(best_car_idx)
                    routes[plan.car_id] = plan.order_ids
                    used_budget += plan.move_time
                    active.remove_many(plan.order_ids)

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


def _best_path_for_car(inst, car, active: ActiveOrders, lam: float, remaining_budget: int) -> PathPlan | None:
    levels = [car.level]
    if car.level > 1:
        levels.append(car.level - 1)
    all_orders = active.iter_levels(levels)
    if not all_orders:
        return None

    total_revenue = max(1, sum(order.revenue for order in inst.orders))
    budget_scale = 1 + inst.moving_budget
    orders = _candidate_orders(all_orders, inst.n_orders)
    orders.sort(key=lambda order: (order.pickup_minute, -order.revenue, order.id))

    val: dict[int, Label | None] = {station: None for station in range(1, inst.n_stations + 1)}
    initial = Label(car.station, 0, 0, 0.0, 0, ())
    val[car.station] = initial
    pool: list[tuple[int, int, Label]] = []
    push_seq = 1
    accepted_labels: list[Label] = []
    _push_relocation_events(inst, pool, initial, lam, budget_scale, remaining_budget, push_seq)
    push_seq += inst.n_stations

    for order in orders:
        while pool and pool[0][0] <= order.pickup_minute - 30:
            _, _, candidate = heapq.heappop(pool)
            _release_candidate(val, candidate)
        best_parent = None
        best_key = None
        label = val[order.pickup_station]
        if label is not None:
            value = label.weight + 3 * order.revenue / total_revenue
            sales = label.sales + order.revenue
            key = (value, sales, -label.move_time, -label.ready)
            best_key = key
            best_parent = (label, value, sales)
        if best_parent is None:
            continue
        label, value, sales = best_parent
        new_label = Label(
            order.return_station,
            order_ready_minute(order),
            label.move_time,
            value,
            sales,
            label.route + (order.id,),
        )
        accepted_labels.append(new_label)
        _push_relocation_events(inst, pool, new_label, lam, budget_scale, remaining_budget, push_seq)
        push_seq += 1
        push_seq += inst.n_stations

    best_label = None
    best_key = None
    for label in accepted_labels:
        key = (label.weight, label.sales, -label.move_time)
        if best_key is None or key > best_key:
            best_key = key
            best_label = label

    if best_label is None:
        return None
    return PathPlan(car.id, list(best_label.route), best_label.move_time, best_label.weight)


def _push_relocation_events(
    inst,
    pool: list[tuple[int, int, Label]],
    label: Label,
    lam: float,
    budget_scale: int,
    remaining_budget: int,
    seq_start: int,
) -> None:
    seq = seq_start
    for station in range(1, inst.n_stations + 1):
        move = inst.move_time[(label.station, station)]
        total_move = label.move_time + move
        if total_move > remaining_budget:
            continue
        relocated = Label(
            station,
            label.ready + move,
            total_move,
            label.weight - lam * move / budget_scale,
            label.sales,
            label.route,
        )
        heapq.heappush(pool, (relocated.ready, seq, relocated))
        seq += 1


def _release_candidate(available: dict[int, Label | None], candidate: Label) -> None:
    current = available[candidate.station]
    if current is None or (candidate.weight, candidate.sales, -candidate.move_time) > (
        current.weight,
        current.sales,
        -current.move_time,
    ):
        available[candidate.station] = candidate


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
    parser.add_argument("--lambdas", default="0", help="ignored; kept for compatibility")
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
