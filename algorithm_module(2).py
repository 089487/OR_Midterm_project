from MTP_lib import *

# ============================================================
# Demand-aware Look-ahead Relocation Heuristic
# Only this file should be submitted as algorithm_module.py.
# ============================================================

BASE_DATE = datetime(2023, 1, 1, 0, 0)
CLEAN_AND_LATE_MIN = 240     # 1 hour possible late return + 3 hours cleaning
READY_BUFFER_MIN = 30        # car must be ready 30 minutes before pickup
BUCKET_MIN = 360             # 6-hour time bucket for demand look-ahead
LOOKAHEAD_BUCKETS = 4         # 24 hours look-ahead under 6-hour buckets
DEFAULT_TIME_LIMIT_SEC = 170.0


def _to_minute(time_str):
    """Convert 'YYYY/MM/DD HH:MM' into minutes after 2023/01/01 00:00."""
    dt = datetime.strptime(time_str.strip(), "%Y/%m/%d %H:%M")
    return int((dt - BASE_DATE).total_seconds() // 60)


def _to_time_str(minute):
    """Convert minutes after 2023/01/01 00:00 into required string format."""
    if minute < 0:
        minute = 0
    dt = BASE_DATE + timedelta(minutes=int(minute))
    return dt.strftime("%Y/%m/%d %H:%M")


def _parse_instance(file_path):
    """Read the instance file.  The parser is intentionally simple and robust."""
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
    future_score[station][car_level][bucket] estimates the future value around a station.
    A car of level L can serve orders requesting level L or L-1.
    """
    horizon_min = nD * 24 * 60
    Q = int(horizon_min // BUCKET_MIN) + LOOKAHEAD_BUCKETS + 3

    demand = [[[0.0 for _ in range(Q + 1)] for __ in range(nL + 1)] for ___ in range(nS + 1)]

    for o in orders:
        q = int(o['pickup_time'] // BUCKET_MIN)
        s = o['pickup_station']
        lev = o['level']
        val = 3.0 * o['revenue']
        # A car of same level can serve it.
        if lev <= nL:
            demand[s][lev][q] += val
        # A car of one higher level can upgrade it.
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
    """Return a large score if this car can serve this order; otherwise None."""
    lev = order['level']
    if not (car_level == lev or car_level == lev + 1):
        return None

    move = T[car_station][order['pickup_station']]
    if used_move + move > B:
        return None

    # must arrive / be ready no later than pickup_time - 30, except time 0 uses max(0, ...)
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

    # future value after completing the order at the return station
    fv = future_score[order['return_station']][car_level][q_after]
    # opportunity cost of removing this car from its current station
    oc = future_score[car_station][car_level][q_now]

    # Budget becomes more precious when already heavily used.
    budget_pressure = 0.0
    if B > 0:
        budget_pressure = used_move / float(B)
    move_penalty = w_move * move * (1.0 + 3.0 * budget_pressure)

    # 3R is the true profit improvement of accepting rather than rejecting an order.
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
    cars_by_level = [[] for _ in range(nL + 2)]

    for cid in car_ids:
        lev = cars[cid]['level']
        car_level[cid] = lev
        car_station[cid] = cars[cid]['station']
        car_available[cid] = 0
        car_history[cid] = []
        if 1 <= lev <= nL:
            cars_by_level[lev].append(cid)

    future_score, max_q = _build_future_score(nS, nL, nD, orders)

    # Parameters: intentionally conservative; relocation has no direct objective cost,
    # but it consumes the global B and may hurt future opportunities.
    w_move = variant.get('w_move', 1.0)
    w_idle = variant.get('w_idle', 0.005)
    w_upgrade = variant.get('w_upgrade', 250.0)
    w_future = variant.get('w_future', 0.015)
    w_opp = variant.get('w_opp', 0.008)

    def best_car_for(order, restricted_car=None):
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
            # Tie-breakers: lower move, lower upgrade, less idle.
            key = (score, -move, -upgrade, -idle)
            if best is None or key > best[0]:
                best = (key, cid, move)
        return best

    def accept_order(order, cid, move):
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
        old_move = 0
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
        car_history[cid] = new_history
        car_station[cid] = new_station
        car_available[cid] = new_available
        return True

    used_move = [0]

    # -------- Phase 1: Initial greedy assignment --------
    if variant.get('sort_mode') == 'time':
        sorted_orders = sorted(orders, key=lambda o: (o['pickup_time'], -o['revenue'] / (o['duration_h'] + 1.0)))
    elif variant.get('sort_mode') == 'revenue':
        sorted_orders = sorted(orders, key=lambda o: (-o['revenue'], o['pickup_time']))
    elif variant.get('sort_mode') == 'density':
        sorted_orders = sorted(orders, key=lambda o: (-o['revenue'] / (o['duration_h'] + 1.0), o['pickup_time']))
    else:
        # bucketed density: mostly chronological but high-value orders within a 6-hour bucket first
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

    # -------- Phase 3: Shortage-bucket repair for rejected orders --------
    rejected = [o for o in orders if assignment[o['id'] - 1] == -1]
    if rejected:
        # Repair decisions should focus on remaining demand, not orders that the
        # greedy phase has already served.
        future_score, max_q = _build_future_score(nS, nL, nD, rejected)

        buckets = {}
        for o in rejected:
            # bucket by pickup station, time quantum, and level
            bkey = (o['pickup_station'], int(o['pickup_time'] // BUCKET_MIN), o['level'])
            if bkey not in buckets:
                buckets[bkey] = {'value': 0.0, 'orders': []}
            buckets[bkey]['value'] += 3.0 * o['revenue']
            buckets[bkey]['orders'].append(o)

        # Prefer buckets with large shortage and low expected relocation effort.
        # This keeps scarce relocation minutes from being spent too early on
        # remote, expensive demand clusters.
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
            # rescue high value orders in high shortage buckets first
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

    # -------- Phase 4: Limited route-insertion repair --------
    # Try to insert high-value rejected orders inside an existing car route.
    # Rebuilding a single car route keeps the move list and timing constraints
    # consistent without requiring a full multi-car re-optimization.
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
    # If a high-value rejected order cannot be inserted directly, try removing one
    # low-value accepted order from a compatible car route and rebuild that route.
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

    # -------- Phase 6: Limited local replacement of the last order of a car --------
    # This repairs some greedy mistakes while keeping schedule feasibility simple.
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
        # Only consider replacing the current last order on a compatible car.
        levels = [order['level']]
        if order['level'] + 1 <= nL:
            levels.append(order['level'] + 1)
        candidate_cars = []
        for lev in levels:
            candidate_cars.extend(cars_by_level[lev])

        # limit the number of cars checked by current feasibility score candidates
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

            # Temporarily rollback this car to the state before its last accepted order.
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

            # Restore before evaluating next candidate.
            car_station[cid] = saved_station
            car_available[cid] = saved_available
            used_move[0] = saved_used

            if res is None:
                continue
            score, new_move, idle, upgrade = res
            # True objective improvement only depends on accepted revenues.
            # Penalty is used to avoid using too much scarce relocation budget.
            budget_pen = 0.0
            if B > 0:
                budget_pen = 0.02 * max(0, new_move - last['move_time']) * (1.0 + 3.0 * used_move[0] / float(B))
            gain = 3.0 * order['revenue'] - 3.0 * old_order['revenue'] - budget_pen
            if gain > best_gain:
                best_gain = gain
                best_tuple = (cid, last, old_oid, new_move)

        if best_tuple is not None:
            cid, last, old_oid, new_move = best_tuple
            # Remove old last order from this car.
            popped = car_history[cid].pop()
            assignment[old_oid - 1] = -1
            if popped['move_idx'] >= 0:
                relocation[popped['move_idx']] = None
                used_move[0] -= popped['move_time']
            car_station[cid] = popped['prev_station']
            car_available[cid] = popped['prev_available']
            # Accept the new order.
            accept_order(order, cid, new_move)

    # Remove cancelled relocation records, if any.
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
    Exact/near-exact DFS for small instances.  It is skipped on large instances.
    Orders are processed by pickup time; a feasible car route must follow this order.
    The search maximizes accepted revenue, equivalent to maximizing the project profit
    because total order revenue is constant.
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

        # Upper bound: even accepting all remaining orders cannot beat the incumbent.
        if accepted_revenue + suffix[idx] <= best_value + 1e-9:
            return

        if idx == nK:
            if accepted_revenue > best_value:
                best_value = accepted_revenue
                best_assignment = assignment[:]
                best_relocation = relocation[:]
            return

        # Memoization: if the same state has been reached with at least as much
        # accepted revenue, this path is dominated.
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
                # Try cheap and non-upgrade assignments first to get strong incumbents.
                options.append((move, upgrade, car_available[cidx], cidx, cid))

        options.sort()

        # Branch 1: accept the order using a feasible car.
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


def heuristic_algorithm(file_path):
    '''
    Return:
        assignment: list of length n_K. assignment[i-1] = car ID or -1.
        relocation: list of [car ID, start station, end station, start time string].
    '''
    start_clock = t.time()
    deadline = start_clock + DEFAULT_TIME_LIMIT_SEC
    nS, nC, nL, nK, nD, B, cars, car_ids, rates, orders, T = _parse_instance(file_path)

    # Several parameter variants are tried.  We keep the plan with the largest
    # accepted revenue; since total rejected revenue is constant, this maximizes
    # the same objective among our generated feasible plans.
    variants = [
        {'sort_mode': 'bucket', 'w_move': 1.0, 'w_idle': 0.003, 'w_upgrade': 250.0, 'w_future': 0.012, 'w_opp': 0.006},
        {'sort_mode': 'time',    'w_move': 1.2, 'w_idle': 0.002, 'w_upgrade': 400.0, 'w_future': 0.010, 'w_opp': 0.008},
        {'sort_mode': 'density', 'w_move': 0.8, 'w_idle': 0.004, 'w_upgrade': 300.0, 'w_future': 0.015, 'w_opp': 0.006},
        {'sort_mode': 'revenue', 'w_move': 1.0, 'w_idle': 0.002, 'w_upgrade': 500.0, 'w_future': 0.010, 'w_opp': 0.010},
    ]

    # For large instances, fewer variants and lighter replacement are safer under
    # the 3-minute limit.  The public upper bound is around 10k orders and 1k cars.
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

    # For small public-like instances, use a bounded exact DFS to improve the plan.
    # For large hidden instances, this is skipped automatically.
    if nK <= 22 and nC <= 12 and t.time() + 2.0 < deadline:
        exact_budget = min(18.0, max(1.0, deadline - t.time() - 1.0))
        best_assignment, best_relocation, best_value = _small_exact_plan(
            nS, nC, nL, nK, nD, B, cars, car_ids, orders, T,
            best_assignment, best_relocation, best_value, time_limit_sec=exact_budget
        )

    # Sorting is not required by the format, but helps any simulator process moves chronologically.
    best_relocation = sorted(best_relocation, key=lambda r: (r[3], r[0], r[1], r[2]))
    return best_assignment, best_relocation
