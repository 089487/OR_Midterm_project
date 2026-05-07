from __future__ import annotations

import argparse
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

from mtp_common import (
    can_serve_level,
    feasible_transition,
    format_minute,
    latest_arrival_for_pickup,
    order_ready_minute,
    parse_instance,
)


def solve_instance(path: str | Path, time_limit: int | None = None, verbose: bool = False) -> dict:
    inst = parse_instance(path)
    orders = inst.orders

    car_arcs: list[tuple[int, int, int]] = []
    order_arcs: list[tuple[int, int, int, int]] = []

    for car in inst.cars:
        for order in orders:
            if not can_serve_level(car.level, order.level):
                continue
            ok, move, _ = feasible_transition(inst, None, car.station, order)
            if ok:
                car_arcs.append((car.id, order.id, move))

    for car in inst.cars:
        for prev in orders:
            if not can_serve_level(car.level, prev.level):
                continue
            for nxt in orders:
                if prev.id == nxt.id or not can_serve_level(car.level, nxt.level):
                    continue
                ok, move, _ = feasible_transition(inst, prev, prev.return_station, nxt)
                if ok:
                    order_arcs.append((car.id, prev.id, nxt.id, move))

    model = gp.Model("midterm_car_rental")
    model.Params.OutputFlag = 1 if verbose else 0
    if time_limit is not None:
        model.Params.TimeLimit = time_limit

    start = model.addVars([(c, k) for c, k, _ in car_arcs], vtype=GRB.BINARY, name="start")
    link = model.addVars([(c, i, j) for c, i, j, _ in order_arcs], vtype=GRB.BINARY, name="link")
    y = model.addVars([o.id for o in orders], vtype=GRB.BINARY, name="accept")

    incoming_by_order = {o.id: [] for o in orders}
    for c, k, _ in car_arcs:
        incoming_by_order[k].append(start[c, k])
    for c, i, j, _ in order_arcs:
        incoming_by_order[j].append(link[c, i, j])

    for order in orders:
        model.addConstr(gp.quicksum(incoming_by_order[order.id]) == y[order.id], name=f"in_{order.id}")

    for car in inst.cars:
        model.addConstr(
            gp.quicksum(start[c, k] for c, k, _ in car_arcs if c == car.id) <= 1,
            name=f"car_{car.id}",
        )
        for order in orders:
            incoming = gp.quicksum(start[cc, k] for cc, k, _ in car_arcs if cc == car.id and k == order.id)
            incoming += gp.quicksum(link[cc, i, j] for cc, i, j, _ in order_arcs if cc == car.id and j == order.id)
            outgoing = gp.quicksum(link[cc, i, j] for cc, i, j, _ in order_arcs if cc == car.id and i == order.id)
            model.addConstr(outgoing <= incoming, name=f"flow_{car.id}_{order.id}")

    model.addConstr(
        gp.quicksum(move * start[c, k] for c, k, move in car_arcs)
        + gp.quicksum(move * link[c, i, j] for c, i, j, move in order_arcs)
        <= inst.moving_budget,
        name="moving_budget",
    )

    model.setObjective(gp.quicksum(order.revenue * y[order.id] for order in orders), GRB.MAXIMIZE)
    model.optimize()

    if model.SolCount == 0:
        raise RuntimeError(f"no solution found for {path}")

    successor: dict[tuple[int, int], int] = {}
    first_by_car: dict[int, int] = {}
    for c, k, _ in car_arcs:
        if start[c, k].X > 0.5:
            first_by_car[c] = k
    for c, i, j, _ in order_arcs:
        if link[c, i, j].X > 0.5:
            successor[c, i] = j

    assignment = [0] * inst.n_orders
    car_routes: dict[int, list[int]] = {car.id: [] for car in inst.cars}
    for car_id, first in first_by_car.items():
        current = first
        while current:
            assignment[current - 1] = car_id
            car_routes[car_id].append(current)
            current = successor.get((car_id, current), 0)

    relocations = build_relocations(inst, car_routes)
    accepted_sales = sum(order.revenue for order in inst.orders if assignment[order.id - 1])
    profit = accepted_sales - 2 * sum(order.revenue for order in inst.orders if not assignment[order.id - 1])
    return {
        "instance": inst,
        "status": model.Status,
        "objective": round(model.ObjVal),
        "profit": profit,
        "assignment": assignment,
        "routes": car_routes,
        "relocations": relocations,
    }


def build_relocations(inst, car_routes: dict[int, list[int]]) -> list[list]:
    by_id = {order.id: order for order in inst.orders}
    relocations: list[list] = []
    for car in inst.cars:
        station = car.station
        ready = 0
        for order_id in car_routes.get(car.id, []):
            order = by_id[order_id]
            move = inst.move_time[(station, order.pickup_station)]
            if move > 0:
                relocations.append(
                    [
                        car.id,
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


def write_plan(solution: dict, out_path: str | Path) -> None:
    inst = solution["instance"]
    assignment = solution["assignment"]
    by_id = {order.id: order for order in inst.orders}
    lines = [
        f"Accepted sales revenue: {solution['objective']}",
        f"Profit with rejection compensation: {solution['profit']}",
        f"Accepted orders: {sum(1 for x in assignment if x)} / {inst.n_orders}",
        f"Moving time used: {sum(row[5] for row in solution['relocations'])} / {inst.moving_budget}",
        "",
        "Assignments",
        "Order ID,Car ID,Requested level,Car level,Upgrade,Pickup station,Return station,Pickup time,Return time,Revenue",
    ]
    cars = {car.id: car for car in inst.cars}
    for order in inst.orders:
        car_id = assignment[order.id - 1]
        if not car_id:
            continue
        car = cars[car_id]
        lines.append(
            ",".join(
                map(
                    str,
                    [
                        order.id,
                        car_id,
                        order.level,
                        car.level,
                        "yes" if car.level > order.level else "no",
                        order.pickup_station,
                        order.return_station,
                        format_minute(inst, order.pickup_minute),
                        format_minute(inst, order.return_minute),
                        order.revenue,
                    ],
                )
            )
        )

    lines += ["", "Rejected orders", "Order ID,Revenue lost,Compensation"]
    for order in inst.orders:
        if not assignment[order.id - 1]:
            lines.append(f"{order.id},{order.revenue},{2 * order.revenue}")

    lines += ["", "Relocations", "Car ID,From,To,Depart,Arrive,Moving minutes,Reason"]
    for row in solution["relocations"]:
        lines.append(",".join(map(str, row)))

    lines += ["", "Routes"]
    for car_id, route in solution["routes"].items():
        if route:
            lines.append(f"Car {car_id}: " + " -> ".join(f"order {order_id}" for order_id in route))
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="*", default=[f"data/instance{i:02d}.txt" for i in range(1, 6)])
    parser.add_argument("--time-limit", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--plans-dir", default="plans")
    args = parser.parse_args()

    Path(args.plans_dir).mkdir(exist_ok=True)
    for path in args.instances:
        solution = solve_instance(path, args.time_limit, args.verbose)
        expected_obj = sum(
            order.revenue for order in solution["instance"].orders if solution["assignment"][order.id - 1]
        )
        out_path = Path(args.plans_dir) / (Path(path).stem + "_optimal_plan.txt")
        write_plan(solution, out_path)
        print(
            f"{path}: accepted_sales={solution['objective']} "
            f"profit={solution['profit']} checked={expected_obj} plan={out_path}"
        )


if __name__ == "__main__":
    main()
