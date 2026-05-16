try:
    from MTP_lib import *
except ModuleNotFoundError:
    from datetime import datetime, timedelta
    import time as t

import argparse
import heapq
import math
import random
import time
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


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


# ============================================================
# Inlined algo1.py
# ============================================================

@dataclass
class CarState:
    car_id: int
    level: int
    station: int
    ready: int = 0
    route: list[int] = field(default_factory=list)


def algo1_heuristic(
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
    # Step 1: Order Prioritization
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
    # Standalone submission cannot rely on the local ip_solver.py module.
    return None
def _choose_insertion(inst, states, order_by_id: dict[int, Order], order: Order, remaining_budget: int):
    best = None
    best_key = None
    for state in states:
        if not can_serve_level(state.level, order.level):
            continue
        
        # Step 2: Chronological Insertion Search
        route_orders = [order_by_id[order_id] for order_id in state.route]
        pickup_times = [route_order.pickup_minute for route_order in route_orders]
        idx = bisect_left(pickup_times, order.pickup_minute)
        
        # Step 3: Feasibility Evaluation
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
        
        # Step 4: Lexicographical Selection (delta_move, upgrade_penalty, idle, car_id)
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


# ============================================================
# Inlined algo5.py
# ============================================================

# ============================================================
# Demand-aware Look-ahead Relocation Heuristic
#
# Main idea:
#   1. Build a feasible greedy assignment.
#   2. Spend relocation budget according to marginal value.
#   3. Repair rejected high-value orders by rebuilding single-car routes.
#
# Submission note:
#   Rename this file to algorithm_module.py before submission.
# ============================================================

BASE_DATE = datetime(2023, 1, 1, 0, 0)
CLEAN_AND_LATE_MIN = 240     # 1 hour possible late return + 3 hours cleaning
READY_BUFFER_MIN = 30        # car must be ready 30 minutes before pickup
BUCKET_MIN = 360             # 6-hour time bucket for demand look-ahead
LOOKAHEAD_BUCKETS = 4         # 24 hours look-ahead under 6-hour buckets
DEFAULT_TIME_LIMIT_SEC = 170.0


def _to_minute(time_str, base_date=None):
    """Convert 'YYYY/MM/DD HH:MM' into minutes after this instance's base date."""
    if base_date is None:
        base_date = BASE_DATE
    dt = datetime.strptime(time_str.strip(), "%Y/%m/%d %H:%M")
    return int((dt - base_date).total_seconds() // 60)


def _to_time_str(minute, base_date=None):
    """Convert minutes after this instance's base date into required string format."""
    if base_date is None:
        base_date = BASE_DATE
    if minute < 0:
        minute = 0
    dt = base_date + timedelta(minutes=int(minute))
    return dt.strftime("%Y/%m/%d %H:%M")


def _parse_instance(file_path):
    """Read the instance file.  The parser is intentionally simple and robust."""
    global BASE_DATE

    with open(file_path, 'r') as fp:
        raw_lines = [line.strip() for line in fp.readlines() if line.strip() != '']

    parts = []
    cur = []
    for line in raw_lines:
        if line.startswith('=========='):
            if cur:
                parts.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        parts.append(cur)

    # Part 0: general parameters
    general = [x.strip() for x in parts[0][1].split(',')]
    nS = int(general[0]); nC = int(general[1]); nL = int(general[2])
    nK = int(general[3]); nD = int(general[4]); B = int(general[5])

    # Part 1: cars
    cars = {}
    car_ids = []
    for row in parts[1][1:]:
        a = [x.strip() for x in row.split(',')]
        cid = int(a[0]); lev = int(a[1]); st = int(a[2])
        cars[cid] = {'id': cid, 'level': lev, 'station': st}
        car_ids.append(cid)

    # Part 2: rates
    rates = {}
    for row in parts[2][1:]:
        a = [x.strip() for x in row.split(',')]
        rates[int(a[0])] = float(a[1])

    # Match mtp_common.py: measure all instance times from the first pickup date.
    first_pickup = min(datetime.strptime(row.split(',')[4].strip(), "%Y/%m/%d %H:%M")
                       for row in parts[3][1:])
    BASE_DATE = datetime(first_pickup.year, first_pickup.month, first_pickup.day)

    # Part 3: orders
    orders = []
    for row in parts[3][1:]:
        a = [x.strip() for x in row.split(',')]
        oid = int(a[0]); lev = int(a[1]); ps = int(a[2]); rs = int(a[3])
        pt = _to_minute(a[4]); rt = _to_minute(a[5])
        duration_h = (rt - pt) / 60.0
        revenue = rates[lev] * duration_h
        orders.append({
            'id': oid,
            'level': lev,
            'pickup_station': ps,
            'return_station': rs,
            'pickup_time': pt,
            'return_time': rt,
            'duration_h': duration_h,
            'revenue': revenue,
            'ready_deadline': max(0, pt - READY_BUFFER_MIN),
            'ready_after_return': rt + CLEAN_AND_LATE_MIN
        })

    # Part 4: moving time matrix, 1-indexed
    T = [[0 for _ in range(nS + 1)] for __ in range(nS + 1)]
    for row in parts[4][1:]:
        a = [x.strip() for x in row.split(',')]
        i = int(a[0]); j = int(a[1]); tm = int(a[2])
        T[i][j] = tm

    orders.sort(key=lambda o: o['id'])

    return nS, nC, nL, nK, nD, B, cars, car_ids, rates, orders, T


def _build_future_score(nS, nL, nD, orders):
    """
    Estimate future demand value by station, car level, and time bucket.

    A car of level L can serve level L orders directly and level L-1 orders
    through a free upgrade.  Each order contributes 3R because accepting it
    improves profit by R - (-2R) = 3R compared with rejecting it.
    """
    horizon_min = nD * 24 * 60
    Q = int(horizon_min // BUCKET_MIN) + LOOKAHEAD_BUCKETS + 3

    demand = [[[0.0 for _ in range(Q + 1)] for __ in range(nL + 1)] for ___ in range(nS + 1)]

    for o in orders:
        q = int(o['pickup_time'] // BUCKET_MIN)
        s = o['pickup_station']
        lev = o['level']
        val = 3.0 * o['revenue']
        # Same-level service receives full future value.
        if lev <= nL:
            demand[s][lev][q] += val
        # One-level upgrades are useful but discounted to preserve high-level cars.
        if lev + 1 <= nL:
            demand[s][lev + 1][q] += 0.75 * val   # upgrade future value is useful but discounted

    future = [[[0.0 for _ in range(Q + 1)] for __ in range(nL + 1)] for ___ in range(nS + 1)]
    for s in range(1, nS + 1):
        for lev in range(1, nL + 1):
            rolling = 0.0
            for q in range(Q - 1, -1, -1):
                rolling += demand[s][lev][q]
                out_q = q + LOOKAHEAD_BUCKETS
                if out_q <= Q:
                    rolling -= demand[s][lev][out_q]
                future[s][lev][q] = rolling
    return future, Q


def _candidate_car_score(order, cid, car_level, car_station, car_available,
                         T, used_move, B, future_score, max_q,
                         w_move, w_idle, w_upgrade, w_future, w_opp):
    """Return a score for assigning one feasible car to one order; otherwise None."""
    lev = order['level']
    if not (car_level == lev or car_level == lev + 1):
        return None

    move = T[car_station][order['pickup_station']]
    if used_move + move > B:
        return None

    # A car must be at the pickup station at least 30 minutes before pickup.
    if car_available + move > order['ready_deadline']:
        return None

    idle = order['ready_deadline'] - (car_available + move)
    upgrade = 1 if car_level == lev + 1 else 0

    q_now = int(car_available // BUCKET_MIN)
    if q_now > max_q:
        q_now = max_q
    q_after = int(order['ready_after_return'] // BUCKET_MIN)
    if q_after > max_q:
        q_after = max_q

    # Value of having this car at the return station after the order.
    fv = future_score[order['return_station']][car_level][q_after]
    # Opportunity cost of removing this car from its current station now.
    oc = future_score[car_station][car_level][q_now]

    # Relocation budget becomes more precious as it is consumed.
    budget_pressure = 0.0
    if B > 0:
        budget_pressure = used_move / float(B)
    move_penalty = w_move * move * (1.0 + 3.0 * budget_pressure)

    # The base value is 3R, the true profit improvement of accept vs. reject.
    score = (3.0 * order['revenue']
             + w_future * fv
             - w_opp * oc
             - move_penalty
             - w_idle * idle
             - w_upgrade * upgrade * max(1, car_level))
    return score, move, idle, upgrade


def _time_left(deadline):
    return deadline is None or t.time() < deadline


def _make_plan(nS, nC, nL, nK, nD, B, cars, car_ids, orders, T, variant, deadline=None):
    """Construct one complete feasible plan under a given parameter variant."""
    assignment = [-1 for _ in range(nK)]
    relocation = []

    car_level = {}
    car_station = {}
    car_available = {}
    car_history = {}  # stack for limited local replacement
    car_staged_move = {}
    cars_by_level = [[] for _ in range(nL + 2)]

    for cid in car_ids:
        lev = cars[cid]['level']
        car_level[cid] = lev
        car_station[cid] = cars[cid]['station']
        car_available[cid] = 0
        car_history[cid] = []
        car_staged_move[cid] = 0
        if 1 <= lev <= nL:
            cars_by_level[lev].append(cid)

    future_score, max_q = _build_future_score(nS, nL, nD, orders)

    # Variant weights control how aggressively this plan spends relocation budget,
    # uses upgrades, tolerates idle time, and values future station demand.
    w_move = variant.get('w_move', 1.0)
    w_idle = variant.get('w_idle', 0.005)
    w_upgrade = variant.get('w_upgrade', 250.0)
    w_future = variant.get('w_future', 0.015)
    w_opp = variant.get('w_opp', 0.008)
    relocation_value_floor = variant.get('relocation_value_floor', None)
    relocation_pressure_mult = variant.get('relocation_pressure_mult', 2.0)

    def initial_min_move(order):
        """Estimate the cheapest initial relocation needed to reach this order."""
        best_move = None
        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)
        for lev in levels:
            for cid in cars_by_level[lev]:
                move = T[cars[cid]['station']][order['pickup_station']]
                if best_move is None or move < best_move:
                    best_move = move
        return best_move if best_move is not None else 999999

    def relocation_value_ok(order, move):
        """Gate low-value relocations when a variant enables relocation-value control."""
        if move <= 0 or relocation_value_floor is None:
            return True
        if B <= 0:
            return False
        pressure = used_move[0] / float(B)
        dynamic_floor = relocation_value_floor * (1.0 + relocation_pressure_mult * pressure)
        return (3.0 * order['revenue']) / float(move) >= dynamic_floor

    def best_car_for(order, restricted_car=None):
        """Find the best currently feasible car for one order under this variant."""
        best = None
        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)

        if restricted_car is not None:
            iterable = [restricted_car]
        else:
            iterable = []
            for lev in levels:
                iterable.extend(cars_by_level[lev])

        for cid in iterable:
            res = _candidate_car_score(
                order, cid, car_level[cid], car_station[cid], car_available[cid],
                T, used_move[0], B, future_score, max_q,
                w_move, w_idle, w_upgrade, w_future, w_opp
            )
            if res is None:
                continue
            score, move, idle, upgrade = res
            if not relocation_value_ok(order, move):
                continue
            # Tie-breakers prefer shorter moves, no upgrade, and less idle time.
            key = (score, -move, -upgrade, -idle)
            if best is None or key > best[0]:
                best = (key, cid, move)
        return best

    def accept_order(order, cid, move):
        """Commit one order to one car and update assignment, relocation, and car state."""
        old_station = car_station[cid]
        old_available = car_available[cid]
        move_idx = -1
        if move > 0:
            move_idx = len(relocation)
            relocation.append([cid, old_station, order['pickup_station'], _to_time_str(old_available)])
            used_move[0] += move

        assignment[order['id'] - 1] = cid
        car_history[cid].append({
            'order_id': order['id'],
            'prev_station': old_station,
            'prev_available': old_available,
            'move_idx': move_idx,
            'move_time': move
        })
        car_station[cid] = order['return_station']
        car_available[cid] = order['ready_after_return']

    def simulate_car_route(cid, route_order_ids):
        """Rebuild one car route from scratch and return its relocation plan if feasible."""
        station = cars[cid]['station']
        available = 0
        total_move = 0
        new_relocation = []
        new_history = []

        for oid in route_order_ids:
            order = orders[oid - 1]
            if not (car_level[cid] == order['level'] or car_level[cid] == order['level'] + 1):
                return None

            move = T[station][order['pickup_station']]
            if available + move > order['ready_deadline']:
                return None

            move_idx = -1
            if move > 0:
                move_idx = len(new_relocation)
                new_relocation.append([cid, station, order['pickup_station'], _to_time_str(available)])
            new_history.append({
                'order_id': order['id'],
                'prev_station': station,
                'prev_available': available,
                'move_idx': move_idx,
                'move_time': move
            })

            total_move += move
            station = order['return_station']
            available = order['ready_after_return']

        return total_move, new_relocation, new_history, station, available

    def replace_car_route(cid, new_route_order_ids):
        """Replace one car's entire route after a successful route simulation."""
        old_move = car_staged_move[cid]
        for h in car_history[cid]:
            old_move += h['move_time']

        sim = simulate_car_route(cid, new_route_order_ids)
        if sim is None:
            return False
        new_move, new_relocation, new_history, new_station, new_available = sim
        if used_move[0] - old_move + new_move > B:
            return False

        for h in car_history[cid]:
            assignment[h['order_id'] - 1] = -1

        for i, r in enumerate(relocation):
            if r is not None and r[0] == cid:
                relocation[i] = None

        base_idx = len(relocation)
        for h in new_history:
            if h['move_idx'] >= 0:
                h['move_idx'] += base_idx
        relocation.extend(new_relocation)

        for oid in new_route_order_ids:
            assignment[oid - 1] = cid

        used_move[0] = used_move[0] - old_move + new_move
        car_staged_move[cid] = 0
        car_history[cid] = new_history
        car_station[cid] = new_station
        car_available[cid] = new_available
        return True

    used_move = [0]

    # -------- Phase 1: Optional initial staging --------
    # Before greedy assignment, move a limited number of idle cars at time 0
    # toward early high-shortage station-level buckets.  This is a general
    # relocation warm start, not a hard-coded station pattern.
    def initial_staging():
        if not variant.get('initial_staging', False) or B <= 0:
            return

        window_min = variant.get('staging_window_min', 24 * 60)
        max_moves = min(variant.get('max_staging_moves', 80), nC)
        budget_cap = B * variant.get('staging_budget_frac', 0.35)

        demand = {}
        earliest = {}
        for o in orders:
            if o['pickup_time'] > window_min:
                continue
            key = (o['pickup_station'], o['level'])
            demand[key] = demand.get(key, 0.0) + 3.0 * o['revenue']
            prev = earliest.get(key)
            if prev is None or o['ready_deadline'] < prev:
                earliest[key] = o['ready_deadline']

        if not demand:
            return

        local_supply = {}
        for cid in car_ids:
            if car_available[cid] != 0:
                continue
            lev = car_level[cid]
            st = car_station[cid]
            local_supply[(st, lev)] = local_supply.get((st, lev), 0) + 1
            if lev > 1:
                local_supply[(st, lev - 1)] = local_supply.get((st, lev - 1), 0) + 1

        bucket_list = []
        for key, val in demand.items():
            station, level = key
            supply = local_supply.get(key, 0)
            shortage = max(0.0, val - supply * variant.get('staging_supply_value', 1200.0))
            if shortage > 0:
                bucket_list.append((shortage, station, level, earliest[key]))
        bucket_list.sort(reverse=True)

        moved = set()
        move_count = 0
        staged_budget = 0
        for shortage, station, level, ready_deadline in bucket_list:
            if not _time_left(deadline):
                break
            if move_count >= max_moves or used_move[0] >= B:
                break

            best = None
            levels = [level]
            if level + 1 <= nL:
                levels.append(level + 1)

            for lev in levels:
                for cid in cars_by_level[lev]:
                    if cid in moved or car_available[cid] != 0:
                        continue
                    if car_station[cid] == station:
                        continue
                    move = T[car_station[cid]][station]
                    if move <= 0:
                        continue
                    if used_move[0] + move > B or staged_budget + move > budget_cap:
                        continue
                    if move > ready_deadline:
                        continue

                    origin_key = (car_station[cid], car_level[cid])
                    origin_pressure = future_score[car_station[cid]][car_level[cid]][0]
                    upgrade = 1 if car_level[cid] == level + 1 else 0
                    score = (shortage
                             - variant.get('staging_move_weight', 2.0) * move
                             - variant.get('staging_origin_weight', 0.01) * origin_pressure
                             - variant.get('staging_upgrade_penalty', 300.0) * upgrade)
                    key = (score, -move, -upgrade, -local_supply.get(origin_key, 0))
                    if best is None or key > best[0]:
                        best = (key, cid, move)

            if best is None or best[0][0] <= 0:
                continue

            _, cid, move = best
            old_station = car_station[cid]
            relocation.append([cid, old_station, station, _to_time_str(0)])
            used_move[0] += move
            staged_budget += move
            move_count += 1
            moved.add(cid)
            car_station[cid] = station
            car_available[cid] = move
            car_staged_move[cid] = move

    initial_staging()

    # -------- Phase 2: Initial greedy assignment --------
    # Build a first feasible plan by scanning orders in the variant's order and
    # assigning each accepted order to its best currently feasible car.
    if variant.get('sort_mode') == 'time':
        sorted_orders = sorted(orders, key=lambda o: (o['pickup_time'], -o['revenue'] / (o['duration_h'] + 1.0)))
    elif variant.get('sort_mode') == 'revenue':
        sorted_orders = sorted(orders, key=lambda o: (-o['revenue'], o['pickup_time']))
    elif variant.get('sort_mode') == 'density':
        sorted_orders = sorted(orders, key=lambda o: (-o['revenue'] / (o['duration_h'] + 1.0), o['pickup_time']))
    elif variant.get('sort_mode') == 'relocation_value':
        sorted_orders = sorted(orders, key=lambda o: (int(o['pickup_time'] // BUCKET_MIN),
                                                      -(3.0 * o['revenue']) / (1.0 + initial_min_move(o)),
                                                      -o['revenue']))
    else:
        # Bucketed density is mostly chronological, but prioritizes valuable orders
        # inside each 6-hour bucket.
        sorted_orders = sorted(orders, key=lambda o: (int(o['pickup_time'] // BUCKET_MIN),
                                                      -o['revenue'] / (o['duration_h'] + 1.0),
                                                      -o['revenue']))

    for order in sorted_orders:
        if not _time_left(deadline):
            break
        best = best_car_for(order)
        if best is not None:
            _, cid, move = best
            accept_order(order, cid, move)

    # -------- Phase 3: Shortage-bucket repair --------
    # Group rejected orders by station, time bucket, and level.  Repair buckets
    # with high shortage value per expected relocation minute first.
    rejected = [o for o in orders if assignment[o['id'] - 1] == -1]
    if rejected:
        # Repair should focus only on demand that the greedy phase did not serve.
        future_score, max_q = _build_future_score(nS, nL, nD, rejected)

        buckets = {}
        for o in rejected:
            # Bucket by pickup station, time quantum, and requested level.
            bkey = (o['pickup_station'], int(o['pickup_time'] // BUCKET_MIN), o['level'])
            if bkey not in buckets:
                buckets[bkey] = {'value': 0.0, 'orders': []}
            buckets[bkey]['value'] += 3.0 * o['revenue']
            buckets[bkey]['orders'].append(o)

        # Prefer large shortage buckets that can be reached with low relocation effort.
        for bkey, b in buckets.items():
            station, _, level = bkey
            best_inbound = None
            levels = [level]
            if level + 1 <= nL:
                levels.append(level + 1)
            for lev in levels:
                for cid in cars_by_level[lev]:
                    move = T[car_station[cid]][station]
                    if best_inbound is None or move < best_inbound:
                        best_inbound = move
            b['priority'] = b['value'] / (1.0 + (best_inbound if best_inbound is not None else 999999.0))

        bucket_list = list(buckets.values())
        bucket_list.sort(key=lambda b: -b['priority'])

        for b in bucket_list:
            if not _time_left(deadline):
                break
            # Inside a shortage bucket, rescue high-revenue orders first.
            b['orders'].sort(key=lambda o: (-o['revenue'], o['pickup_time']))
            for order in b['orders']:
                if not _time_left(deadline):
                    break
                if assignment[order['id'] - 1] != -1:
                    continue
                best = best_car_for(order)
                if best is not None:
                    _, cid, move = best
                    accept_order(order, cid, move)

    # -------- Phase 4: Route-insertion repair --------
    # Insert high-value rejected orders into existing single-car routes when this
    # can be done without removing any accepted order.  Every candidate route is
    # rebuilt from scratch, so timing and relocation records stay consistent.
    rejected = [o for o in orders if assignment[o['id'] - 1] == -1]
    rejected.sort(key=lambda o: -o['revenue'])
    max_insert_rejected = min(len(rejected), variant.get('max_insert_rejected', 120))
    max_insert_cars = variant.get('max_insert_cars', 80)
    max_insert_positions = variant.get('max_insert_positions', 8)

    for order in rejected[:max_insert_rejected]:
        if not _time_left(deadline):
            break
        if assignment[order['id'] - 1] != -1:
            continue

        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)

        candidate_cars = []
        for lev in levels:
            candidate_cars.extend(cars_by_level[lev])
        candidate_cars.sort(key=lambda cid: (
            T[car_station[cid]][order['pickup_station']],
            car_available[cid]
        ))

        best_gain = 0.0
        best_route = None
        checked = 0
        for cid in candidate_cars:
            if not _time_left(deadline):
                break
            if checked >= max_insert_cars:
                break
            checked += 1

            route = [h['order_id'] for h in car_history[cid]]
            if order['id'] in route:
                continue

            old_move = 0
            for h in car_history[cid]:
                old_move += h['move_time']

            if len(route) == 0:
                positions = [0]
            else:
                chronological_pos = 0
                while (chronological_pos < len(route)
                       and orders[route[chronological_pos] - 1]['pickup_time'] <= order['pickup_time']):
                    chronological_pos += 1
                positions = []
                for delta in range(0, len(route) + 1):
                    left = chronological_pos - delta
                    right = chronological_pos + delta
                    if 0 <= left <= len(route) and left not in positions:
                        positions.append(left)
                    if 0 <= right <= len(route) and right not in positions:
                        positions.append(right)
                    if len(positions) >= max_insert_positions:
                        break

            for pos in positions:
                trial_route = route[:pos] + [order['id']] + route[pos:]
                sim = simulate_car_route(cid, trial_route)
                if sim is None:
                    continue
                new_move = sim[0]
                if used_move[0] - old_move + new_move > B:
                    continue

                budget_pen = 0.0
                if B > 0:
                    budget_pen = 0.02 * max(0, new_move - old_move) * (1.0 + 3.0 * used_move[0] / float(B))
                gain = 3.0 * order['revenue'] - budget_pen
                if gain > best_gain:
                    best_gain = gain
                    best_route = (cid, trial_route)

        if best_route is not None:
            cid, trial_route = best_route
            replace_car_route(cid, trial_route)

    # -------- Phase 5: One-removal route repair --------
    # If direct insertion fails, try replacing one low-value accepted order inside
    # a compatible car route with one high-value rejected order.
    rejected = [o for o in orders if assignment[o['id'] - 1] == -1]
    rejected.sort(key=lambda o: -o['revenue'])
    max_swap_rejected = min(len(rejected), variant.get('max_swap_rejected', 100))
    max_swap_cars = variant.get('max_swap_cars', 70)
    max_swap_removals = variant.get('max_swap_removals', 5)
    max_swap_positions = variant.get('max_swap_positions', 6)

    for order in rejected[:max_swap_rejected]:
        if not _time_left(deadline):
            break
        if assignment[order['id'] - 1] != -1:
            continue

        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)

        candidate_cars = []
        for lev in levels:
            candidate_cars.extend(cars_by_level[lev])
        candidate_cars.sort(key=lambda cid: (
            T[car_station[cid]][order['pickup_station']],
            car_available[cid]
        ))

        best_gain = 0.0
        best_route = None
        checked = 0
        for cid in candidate_cars:
            if not _time_left(deadline):
                break
            if checked >= max_swap_cars:
                break
            checked += 1

            route = [h['order_id'] for h in car_history[cid]]
            if not route or order['id'] in route:
                continue

            old_move = 0
            for h in car_history[cid]:
                old_move += h['move_time']

            removable = []
            for oid in route:
                old_order = orders[oid - 1]
                if old_order['revenue'] < order['revenue']:
                    removable.append((old_order['revenue'], oid))
            removable.sort()

            for _, remove_oid in removable[:max_swap_removals]:
                if not _time_left(deadline):
                    break
                base_route = [oid for oid in route if oid != remove_oid]
                removed_order = orders[remove_oid - 1]

                chronological_pos = 0
                while (chronological_pos < len(base_route)
                       and orders[base_route[chronological_pos] - 1]['pickup_time'] <= order['pickup_time']):
                    chronological_pos += 1

                positions = []
                for delta in range(0, len(base_route) + 1):
                    left = chronological_pos - delta
                    right = chronological_pos + delta
                    if 0 <= left <= len(base_route) and left not in positions:
                        positions.append(left)
                    if 0 <= right <= len(base_route) and right not in positions:
                        positions.append(right)
                    if len(positions) >= max_swap_positions:
                        break

                for pos in positions:
                    trial_route = base_route[:pos] + [order['id']] + base_route[pos:]
                    sim = simulate_car_route(cid, trial_route)
                    if sim is None:
                        continue
                    new_move = sim[0]
                    if used_move[0] - old_move + new_move > B:
                        continue

                    budget_pen = 0.0
                    if B > 0:
                        budget_pen = 0.02 * max(0, new_move - old_move) * (1.0 + 3.0 * used_move[0] / float(B))
                    gain = 3.0 * (order['revenue'] - removed_order['revenue']) - budget_pen
                    if gain > best_gain:
                        best_gain = gain
                        best_route = (cid, trial_route)

        if best_route is not None:
            cid, trial_route = best_route
            replace_car_route(cid, trial_route)

    # -------- Phase 6: Last-order replacement repair --------
    # As a cheaper final local search, replace only the current last order of a
    # compatible car route.  This avoids rebuilding later orders.
    rejected = [o for o in orders if assignment[o['id'] - 1] == -1]
    rejected.sort(key=lambda o: -o['revenue'])
    max_repl_rejected = min(len(rejected), variant.get('max_repl_rejected', 300))
    for order in rejected[:max_repl_rejected]:
        if not _time_left(deadline):
            break
        if assignment[order['id'] - 1] != -1:
            continue
        best_gain = 0.0
        best_tuple = None
        # Only the route's last order is considered in this phase.
        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)
        candidate_cars = []
        for lev in levels:
            candidate_cars.extend(cars_by_level[lev])

        # Keep this final repair bounded for large instances.
        checked = 0
        for cid in candidate_cars:
            if not _time_left(deadline):
                break
            if checked >= variant.get('max_repl_cars', 200):
                break
            checked += 1
            if not car_history[cid]:
                continue
            last = car_history[cid][-1]
            old_oid = last['order_id']
            old_order = orders[old_oid - 1]

            # Temporarily roll this car back to the state before its last order.
            saved_station = car_station[cid]
            saved_available = car_available[cid]
            saved_used = used_move[0]

            car_station[cid] = last['prev_station']
            car_available[cid] = last['prev_available']
            used_move[0] -= last['move_time']

            res = _candidate_car_score(
                order, cid, car_level[cid], car_station[cid], car_available[cid],
                T, used_move[0], B, future_score, max_q,
                w_move, w_idle, w_upgrade, w_future, w_opp
            )

            # Restore the car state before evaluating the next candidate.
            car_station[cid] = saved_station
            car_available[cid] = saved_available
            used_move[0] = saved_used

            if res is None:
                continue
            score, new_move, idle, upgrade = res
            # True objective improvement is based on accepted revenue; the small
            # budget penalty discourages spending scarce relocation minutes late.
            budget_pen = 0.0
            if B > 0:
                budget_pen = 0.02 * max(0, new_move - last['move_time']) * (1.0 + 3.0 * used_move[0] / float(B))
            gain = 3.0 * order['revenue'] - 3.0 * old_order['revenue'] - budget_pen
            if gain > best_gain:
                best_gain = gain
                best_tuple = (cid, last, old_oid, new_move)

        if best_tuple is not None:
            cid, last, old_oid, new_move = best_tuple
            # Remove the old last order from this car.
            popped = car_history[cid].pop()
            assignment[old_oid - 1] = -1
            if popped['move_idx'] >= 0:
                relocation[popped['move_idx']] = None
                used_move[0] -= popped['move_time']
            car_station[cid] = popped['prev_station']
            car_available[cid] = popped['prev_available']
            # Accept the replacement order.
            accept_order(order, cid, new_move)

    # -------- Phase 7: Finalize this variant plan --------
    # Remove relocation records canceled by route replacement and compute the
    # accepted revenue used to compare this variant with other variants.
    relocation = [r for r in relocation if r is not None]

    accepted_revenue = 0.0
    for o in orders:
        if assignment[o['id'] - 1] != -1:
            accepted_revenue += o['revenue']
    return assignment, relocation, accepted_revenue



def _small_exact_plan(nS, nC, nL, nK, nD, B, cars, car_ids, orders, T,
                      initial_assignment=None, initial_relocation=None, initial_value=-1.0,
                      time_limit_sec=18.0):
    """
    Bounded exact DFS for small instances only.

    The search maximizes accepted revenue, which is equivalent to maximizing
    profit for a fixed instance.  It is skipped for large hidden instances and
    protected by a short time limit.
    """
    if nK > 22 or nC > 12:
        return initial_assignment, initial_relocation, initial_value

    start_clock = t.time()
    sorted_orders = sorted(orders, key=lambda o: (o['pickup_time'], -o['revenue']))

    suffix = [0.0 for _ in range(nK + 1)]
    for i in range(nK - 1, -1, -1):
        suffix[i] = suffix[i + 1] + sorted_orders[i]['revenue']

    car_levels = [cars[cid]['level'] for cid in car_ids]
    car_station = [cars[cid]['station'] for cid in car_ids]
    car_available = [0 for _ in car_ids]

    assignment = [-1 for _ in range(nK)]
    relocation = []

    best_value = initial_value
    best_assignment = initial_assignment[:] if initial_assignment is not None else assignment[:]
    best_relocation = initial_relocation[:] if initial_relocation is not None else []

    seen = {}

    def dfs(idx, used_move, accepted_revenue):
        nonlocal best_value, best_assignment, best_relocation

        if t.time() - start_clock > time_limit_sec:
            return

        # Upper bound: prune if even accepting all remaining orders cannot win.
        if accepted_revenue + suffix[idx] <= best_value + 1e-9:
            return

        if idx == nK:
            if accepted_revenue > best_value:
                best_value = accepted_revenue
                best_assignment = assignment[:]
                best_relocation = relocation[:]
            return

        # Dominance memoization: same state with lower accepted revenue is useless.
        state_key = (idx, used_move, tuple(zip(car_available, car_station)))
        prev = seen.get(state_key)
        if prev is not None and prev >= accepted_revenue - 1e-9:
            return
        seen[state_key] = accepted_revenue

        o = sorted_orders[idx]
        options = []
        for cidx, cid in enumerate(car_ids):
            cl = car_levels[cidx]
            if not (cl == o['level'] or cl == o['level'] + 1):
                continue
            move = T[car_station[cidx]][o['pickup_station']]
            if used_move + move > B:
                continue
            if car_available[cidx] + move <= o['ready_deadline']:
                upgrade = 1 if cl == o['level'] + 1 else 0
                # Try cheap, non-upgrade assignments first for stronger incumbents.
                options.append((move, upgrade, car_available[cidx], cidx, cid))

        options.sort()

        # Branch 1: accept the order using one feasible car.
        for move, upgrade, avail, cidx, cid in options:
            old_station = car_station[cidx]
            old_available = car_available[cidx]
            if move > 0:
                relocation.append([cid, old_station, o['pickup_station'], _to_time_str(old_available)])

            assignment[o['id'] - 1] = cid
            car_station[cidx] = o['return_station']
            car_available[cidx] = o['ready_after_return']

            dfs(idx + 1, used_move + move, accepted_revenue + o['revenue'])

            car_station[cidx] = old_station
            car_available[cidx] = old_available
            assignment[o['id'] - 1] = -1
            if move > 0:
                relocation.pop()

        # Branch 2: reject the order.
        dfs(idx + 1, used_move, accepted_revenue)

    dfs(0, 0, 0.0)
    return best_assignment, best_relocation, best_value


def algo5_heuristic(file_path, raw_test: bool = False):
    '''
    Return:
        assignment: list of length n_K. assignment[i-1] = car ID or -1.
        relocation: list of [car ID, start station, end station, start time string].
    '''
    start_clock = t.time()
    deadline = start_clock + DEFAULT_TIME_LIMIT_SEC
    nS, nC, nL, nK, nD, B, cars, car_ids, rates, orders, T = _parse_instance(file_path)

    # Try several complementary variants and keep the largest accepted revenue.
    # For a fixed instance, this is equivalent to keeping the largest profit.
    variants = [
        {'sort_mode': 'bucket',  'w_move': 0.7, 'w_idle': 0.003, 'w_upgrade': 250.0, 'w_future': 0.012, 'w_opp': 0.006,
         'initial_staging': True, 'staging_budget_frac': 0.35, 'max_staging_moves': 120},
        {'sort_mode': 'relocation_value', 'w_move': 0.6, 'w_idle': 0.002, 'w_upgrade': 350.0, 'w_future': 0.012, 'w_opp': 0.008,
         'relocation_value_floor': 2.0, 'relocation_pressure_mult': 2.5},
        {'sort_mode': 'revenue', 'w_move': 0.8, 'w_idle': 0.002, 'w_upgrade': 500.0, 'w_future': 0.010, 'w_opp': 0.010},
        {'sort_mode': 'time',    'w_move': 1.2, 'w_idle': 0.002, 'w_upgrade': 400.0, 'w_future': 0.010, 'w_opp': 0.008},
        {'sort_mode': 'density', 'w_move': 0.8, 'w_idle': 0.004, 'w_upgrade': 300.0, 'w_future': 0.015, 'w_opp': 0.006},
    ]

    # Large instances use fewer variants and bounded repair searches to stay under
    # the 3-minute grading limit.
    if nK > 8000 or nC > 900 or nD > 60:
        variants = variants[:2]
        for var in variants:
            var['max_repl_rejected'] = 120
            var['max_repl_cars'] = 80
            var['max_insert_rejected'] = 80
            var['max_insert_cars'] = 50
            var['max_insert_positions'] = 6
            var['max_swap_rejected'] = 60
            var['max_swap_cars'] = 40
            var['max_swap_removals'] = 4
            var['max_swap_positions'] = 5
    elif nK > 4000 or nC > 700 or nD > 30:
        variants = variants[:2]
        for var in variants:
            var['max_repl_rejected'] = 180
            var['max_repl_cars'] = 120
            var['max_insert_rejected'] = 100
            var['max_insert_cars'] = 70
            var['max_insert_positions'] = 6
            var['max_swap_rejected'] = 80
            var['max_swap_cars'] = 50
            var['max_swap_removals'] = 4
            var['max_swap_positions'] = 5

    best_assignment = [-1 for _ in range(nK)]
    best_relocation = []
    best_value = -1.0

    for var in variants:
        if not _time_left(deadline):
            break
        assignment, relocation, accepted_revenue = _make_plan(
            nS, nC, nL, nK, nD, B, cars, car_ids, orders, T, var, deadline
        )
        if accepted_revenue > best_value:
            best_value = accepted_revenue
            best_assignment = assignment
            best_relocation = relocation

    # Small public-like instances get a bounded exact improvement pass.
    if not raw_test and nK <= 22 and nC <= 12 and t.time() + 2.0 < deadline:
        exact_budget = min(18.0, max(1.0, deadline - t.time() - 1.0))
        best_assignment, best_relocation, best_value = _small_exact_plan(
            nS, nC, nL, nK, nD, B, cars, car_ids, orders, T,
            best_assignment, best_relocation, best_value, time_limit_sec=exact_budget
        )

    # Chronological move order is not required by format, but helps simulators.
    best_relocation = sorted(best_relocation, key=lambda r: (r[3], r[0], r[1], r[2]))
    return best_assignment, best_relocation


# ============================================================
# Inlined heuristic_algo3.py helpers
# ============================================================

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
    seed: int = 1142,
    temperature: float = 0.35,
    batch_size: int = 5,
    raw_test: bool = False,
):
    """Algo1 plus release-multiple-cars local search.

    Start from Algo1, then repeatedly sample low-efficiency trajectories,
    release them, shuffle those cars, and rebuild them with a top-10 station
    sweep DP. The DP score is route revenue divided by one plus route moving
    time, so there is no inner lambda loop.
    """
    inst = parse_instance(instance_file)
    deadline = time.perf_counter() + max_seconds
    rng = random.Random(seed)
    assignment, _ = algo1_heuristic(instance_file, raw_test=raw_test)
    ctx = _build_context(inst)
    routes = _assignment_to_routes(inst, assignment)
    current_routes = {car_id: route[:] for car_id, route in routes.items()}
    current_profit = _profit_from_routes(inst, current_routes)
    best_routes = {car_id: route[:] for car_id, route in current_routes.items()}
    best_profit = _profit_from_routes(inst, best_routes)

    for _ in range(iterations):
        if time.perf_counter() >= deadline:
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
        if used_without_car > inst.moving_budget:
            continue

        assigned_elsewhere = {
            order_id
            for cid, route in base_routes.items()
            if cid not in car_ids
            for order_id in route
        }
        available = {order.id for order in inst.orders if order.id not in assigned_elsewhere}
        available.update(released_orders)

        trial_routes = {cid: route[:] for cid, route in base_routes.items()}
        rng.shuffle(car_ids)
        used_budget = used_without_car
        for car_id in car_ids:
            if time.perf_counter() >= deadline:
                break
            remaining_budget = inst.moving_budget - used_budget
            if remaining_budget <= 0:
                break
            car = ctx.car_by_id[car_id]
            plan = _best_path_for_car_topk(inst, ctx, car, available, remaining_budget)
            trial_routes[car_id] = [] if plan is None else plan.order_ids
            used_budget += 0 if plan is None else plan.move_time
            available.difference_update(trial_routes[car_id])

        moving = _moving_from_routes(inst, ctx, trial_routes)
        if moving > inst.moving_budget:
            continue
        profit = _profit_from_routes(inst, trial_routes)
        if profit < current_profit:
            continue
        current_routes = trial_routes
        current_profit = profit
        if current_profit > best_profit:
            best_routes = {car_id: route[:] for car_id, route in current_routes.items()}
            best_profit = current_profit

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


def _sample_routes_by_softmax_efficiency(
    inst,
    ctx: Algo3Context,
    routes: dict[int, list[int]],
    rng: random.Random,
    temperature: float,
    batch_size: int,
) -> list[int]:
    order_by_id = {order.id: order for order in inst.orders}
    candidates: list[tuple[int, float]] = []
    for car_id, route in routes.items():
        if not route:
            continue
        reward = sum(order_by_id[order_id].revenue for order_id in route)
        move_time = _route_move_time(ctx, car_id, route)
        candidates.append((car_id, reward / (1 + move_time)))
    if not candidates:
        return []
    values = [value for _, value in candidates]
    min_value = min(values)
    avg_value = max(1e-9, sum(values) / len(values))
    scale = max(1e-9, abs(avg_value) * max(temperature, 1e-6))
    pool = [(car_id, math.exp(-(value - min_value) / scale)) for car_id, value in candidates]
    chosen: list[int] = []
    for _ in range(min(batch_size, len(pool))):
        total = sum(weight for _, weight in pool)
        if total <= 0:
            break
        pick = rng.random() * total
        cumulative = 0.0
        selected_idx = len(pool) - 1
        for idx, (_, weight) in enumerate(pool):
            cumulative += weight
            if cumulative >= pick:
                selected_idx = idx
                break
        car_id, _ = pool.pop(selected_idx)
        chosen.append(car_id)
    return chosen


def _route_move_time(ctx: Algo3Context, car_id: int, route: list[int]) -> int:
    station = ctx.car_by_id[car_id].station
    total = 0
    for order_id in route:
        order = ctx.order_by_id[order_id]
        total += ctx.move_matrix[station][order.pickup_station]
        station = order.return_station
    return total


def _best_path_for_car_topk(
    inst,
    ctx: Algo3Context,
    car,
    available: set[int],
    remaining_budget: int,
) -> Plan | None:
    orders = [
        order
        for order in inst.orders
        if order.id in available and can_serve_level(car.level, order.level)
    ]
    orders.sort(key=lambda order: (order.pickup_minute, -order.revenue, order.id))
    if not orders:
        return None

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
            weight = sales / (1 + total_move)
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


# ============================================================
# Inlined heuristic_algo4.py helpers
# ============================================================

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
    assignment, _ = algo1_heuristic(instance_file, raw_test=raw_test)
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
    model = Model("algo4_local_repair")
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
        model.addConstr(quicksum(incoming_by_order[order.id]) == y[order.id])

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
        model.addConstr(quicksum(start[c, k] for c, k, _ in car_arcs if c == car_id) <= 1)
        for order in orders:
            incoming = quicksum(incoming_by_car_order[car_id, order.id])
            outgoing = quicksum(outgoing_by_car_order[car_id, order.id])
            model.addConstr(outgoing <= incoming)

    model.addConstr(
        quicksum(move * start[c, k] for c, k, move in car_arcs)
        + quicksum(move * link[c, i, j] for c, i, j, move in order_arcs)
        <= remaining_budget
    )
    model.setObjective(quicksum(order_by_id[k].revenue * y[k] for k in y.keys()), GRB.MAXIMIZE)
    try:
        model.optimize()
    except GurobiError:
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


# ============================================================
# Union submission entry points
# ============================================================

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

    select_candidate_orders, solve_local_ip = _select_candidate_orders, _solve_local_ip
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
