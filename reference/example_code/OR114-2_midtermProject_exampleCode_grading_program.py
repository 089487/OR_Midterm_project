'''
You do not need to change the code in this file.
You only need to ensure that the TAs can run your algorithm here.
'''
try:
    from MTP_lib import *
except ModuleNotFoundError:
    import os
    import time as t
    from datetime import datetime

    import numpy as np
    import pandas as pd
from algorithm_module import heuristic_algorithm
from mtp_common import (
    can_serve_level,
    format_minute,
    latest_arrival_for_pickup,
    order_ready_minute,
    parse_instance,
)

def check_format(assignment, relocation):
    for i in assignment:
        if not isinstance(i, int):
            return False

    for relocate in relocation:
        if len(relocate) != 4:
            return False

        if not isinstance(relocate[0], int) or not isinstance(relocate[1], int) or not isinstance(relocate[2], int):
            return False

        date_format = "%Y/%m/%d %H:%M"

        try:
            dateObject = datetime.strptime(relocate[3], date_format)
        except ValueError:
            return False

        import re
        r = re.compile('.{4}/.{2}/.{2} .{2}:.{2}')
        if r.match(relocate[3]) is None:
            return False

    return True

def is_accepted(car_id):
    return car_id is not None and int(car_id) > 0

def objective_value(inst, assignment):
    accepted = sum(o.revenue for o, c in zip(inst.orders, assignment) if is_accepted(c))
    total = sum(o.revenue for o in inst.orders)
    return accepted - 2 * (total - accepted)

def find_obj_value(file_path, assignment, relocation):
    inst = parse_instance(file_path)
    violations = []

    if len(assignment) != inst.n_orders:
        violations.append(f"assignment length {len(assignment)} != n_K {inst.n_orders}")

    if not check_format(assignment, relocation):
        violations.append("format error")

    cars = {c.id: c for c in inst.cars}
    orders = {o.id: o for o in inst.orders}
    by_car = {c.id: [] for c in inst.cars}

    for order_id, car_id in enumerate(assignment, start=1):
        if car_id == -1:
            continue
        if not is_accepted(car_id):
            violations.append(f"order {order_id}: rejected value should be -1, got {car_id}")
            continue
        if int(car_id) not in cars:
            violations.append(f"order {order_id}: unknown car {car_id}")
            continue
        car = cars[int(car_id)]
        order = orders[order_id]
        if not can_serve_level(car.level, order.level):
            violations.append(
                f"order {order_id}: car {car.id} level {car.level} cannot serve level {order.level}"
            )
        by_car[car.id].append(order)

    expected_relocation = []
    moving_time = 0
    for car_id, car_orders in by_car.items():
        car_orders.sort(key=lambda o: (o.pickup_minute, o.id))
        station = cars[car_id].station
        ready = 0
        for order in car_orders:
            move = inst.move_time[(station, order.pickup_station)]
            same_station_at_start = ready == 0 and move == 0 and order.pickup_minute == 0
            if not same_station_at_start and ready + move > latest_arrival_for_pickup(order):
                violations.append(
                    f"car {car_id} -> order {order.id}: ready {ready} + move {move} "
                    f"> latest {latest_arrival_for_pickup(order)}"
                )
            if move > 0:
                expected_relocation.append([car_id, station, order.pickup_station, format_minute(inst, ready)])
            moving_time += move
            station = order.return_station
            ready = order_ready_minute(order)

    if moving_time > inst.moving_budget:
        violations.append(f"moving budget exceeded: {moving_time} > {inst.moving_budget}")

    normalized_relocation = sorted(relocation, key=lambda row: (row[0], row[3], row[1], row[2]))
    expected_relocation = sorted(expected_relocation, key=lambda row: (row[0], row[3], row[1], row[2]))
    if normalized_relocation != expected_relocation:
        violations.append(
            f"relocation mismatch: got {len(normalized_relocation)} moves, "
            f"expected {len(expected_relocation)} moves"
        )

    return len(violations) == 0, objective_value(inst, assignment), moving_time, violations

if __name__ == '__main__':

    # read all instances (.txt file) under data folder
    all_data_list = os.listdir('data')

    # evaluate all instances
    result_df = pd.DataFrame(columns = ['Data name', 'Time', 'Profit', 'Feasibility', 'Moving time', 'Accepted orders', 'Error'])

    for file_name in all_data_list:

        start_time = t.time()
        profit = np.nan
        feasibility = False
        moving_time = np.nan
        accepted_orders = np.nan
        error = ""

        try:
            '''
            1. We will import your algorithm here and give you file_path (e.g.,'data/instance01.txt') as the function argument.
            2. You need to return two lists "assignment" and "relocation".
            '''
            file_path = 'data/' + file_name
            assignment, relocation = heuristic_algorithm(file_path)

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print("the algorithm has errors")

        end_time = t.time()
        spent_time = end_time - start_time

        try:
            '''
            We will check the format, feasibility, and calculate the objective values here.
            '''
            if not check_format(assignment, relocation):
                print("the format has errors")

            feasibility, profit, moving_time, violations = find_obj_value(file_path, assignment, relocation)
            accepted_orders = sum(1 for car_id in assignment if is_accepted(car_id))
            error = "; ".join(violations[:5])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print("the algorithm has errors")


        result_df = pd.concat([result_df, pd.DataFrame([{'Data name': file_name,
                                      'Time': spent_time,
                                      'Profit': profit,
                                      'Feasibility': feasibility,
                                      'Moving time': moving_time,
                                      'Accepted orders': accepted_orders,
                                      'Error': error}])], ignore_index = True)

# output result
result_df.to_csv('result.csv', index = False)
