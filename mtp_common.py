from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


TIME_FMT = "%Y/%m/%d %H:%M"
READY_BEFORE_PICKUP = 30
RETURN_DELAY_AND_CLEANING = 240


@dataclass(frozen=True)
class Car:
    id: int
    level: int
    station: int


@dataclass(frozen=True)
class Order:
    id: int
    level: int
    pickup_station: int
    return_station: int
    pickup_minute: int
    return_minute: int
    revenue: int


@dataclass(frozen=True)
class Instance:
    n_stations: int
    n_cars: int
    n_levels: int
    n_orders: int
    n_days: int
    moving_budget: int
    cars: list[Car]
    rates: dict[int, int]
    orders: list[Order]
    move_time: dict[tuple[int, int], int]
    start: datetime


def _read_sections(path: str | Path) -> list[list[list[str]]]:
    sections: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "==========":
            if current:
                sections.append(current)
                current = []
            continue
        current.append([cell.strip() for cell in line.split(",")])
    if current:
        sections.append(current)
    if len(sections) != 5:
        raise ValueError(f"expected 5 sections in {path}, got {len(sections)}")
    return sections


def parse_instance(path: str | Path) -> Instance:
    sections = _read_sections(path)
    n_stations, n_cars, n_levels, n_orders, n_days, budget = map(int, sections[0][1])

    cars = [Car(int(row[0]), int(row[1]), int(row[2])) for row in sections[1][1:]]
    rates = {int(row[0]): int(row[1]) for row in sections[2][1:]}

    start = datetime(2023, 1, 1)
    orders: list[Order] = []
    for row in sections[3][1:]:
        pickup = datetime.strptime(row[4], TIME_FMT)
        ret = datetime.strptime(row[5], TIME_FMT)
        pickup_minute = int((pickup - start).total_seconds() // 60)
        return_minute = int((ret - start).total_seconds() // 60)
        hours = (return_minute - pickup_minute) // 60
        level = int(row[1])
        orders.append(
            Order(
                id=int(row[0]),
                level=level,
                pickup_station=int(row[2]),
                return_station=int(row[3]),
                pickup_minute=pickup_minute,
                return_minute=return_minute,
                revenue=rates[level] * hours,
            )
        )

    move_time = {(int(row[0]), int(row[1])): int(row[2]) for row in sections[4][1:]}
    return Instance(
        n_stations=n_stations,
        n_cars=n_cars,
        n_levels=n_levels,
        n_orders=n_orders,
        n_days=n_days,
        moving_budget=budget,
        cars=sorted(cars, key=lambda c: c.id),
        rates=rates,
        orders=sorted(orders, key=lambda o: o.id),
        move_time=move_time,
        start=start,
    )


def can_serve_level(car_level: int, order_level: int) -> bool:
    return car_level == order_level or car_level == order_level + 1


def order_ready_minute(order: Order) -> int:
    return order.return_minute + RETURN_DELAY_AND_CLEANING


def latest_arrival_for_pickup(order: Order) -> int:
    return order.pickup_minute - READY_BEFORE_PICKUP


def feasible_transition(inst: Instance, prev: Order | None, station: int, nxt: Order) -> tuple[bool, int, int]:
    move = inst.move_time[(station, nxt.pickup_station)]
    ready = 0 if prev is None else order_ready_minute(prev)
    if prev is None and move == 0 and nxt.pickup_minute == 0:
        feasible = True
    else:
        feasible = ready + move <= latest_arrival_for_pickup(nxt)
    return feasible, move, ready


def objective_from_assignment(inst: Instance, assignment: Iterable[int]) -> int:
    accepted = {order.id for order, car_id in zip(inst.orders, assignment) if car_id}
    accepted_revenue = sum(order.revenue for order in inst.orders if order.id in accepted)
    total_revenue = sum(order.revenue for order in inst.orders)
    return accepted_revenue - 2 * (total_revenue - accepted_revenue)


def format_minute(inst: Instance, minute: int) -> str:
    return (inst.start.replace() + __import__("datetime").timedelta(minutes=minute)).strftime(TIME_FMT)
