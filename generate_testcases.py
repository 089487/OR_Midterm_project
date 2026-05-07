from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path


def weighted_choice(items: list[int], weights: list[float]) -> int:
    return random.choices(items, weights=weights, k=1)[0]


def write_instance(
    path: Path,
    *,
    n_stations: int,
    n_cars: int,
    n_levels: int,
    n_orders: int,
    n_days: int,
    budget: int,
    level_weights: list[float],
    flow: str,
) -> None:
    start = datetime(2023, 1, 1)
    rates = {level: 100 * (2 ** (level - 1)) for level in range(1, n_levels + 1)}
    lines: list[str] = ["n_S,n_C,n_L,n_K,n_D,B", f"{n_stations},{n_cars},{n_levels},{n_orders},{n_days},{budget}", "=========="]

    lines.append("Car ID,Level,Initial station")
    for car_id in range(1, n_cars + 1):
        level = 1 + min(n_levels - 1, (car_id - 1) * n_levels // n_cars)
        station = random.randint(1, n_stations)
        lines.append(f"{car_id},{level},{station}")
    lines.append("==========")

    lines.append("Car level,Hour rate")
    for level, rate in rates.items():
        lines.append(f"{level},{rate}")
    lines.append("==========")

    move = make_move_matrix(n_stations)
    lines.append("Order ID,Level,Pick-up station,Return station,Pick-up time,Return time")
    for order_id in range(1, n_orders + 1):
        level = weighted_choice(list(range(1, n_levels + 1)), level_weights)
        pickup_station, return_station = choose_stations(n_stations, flow)
        latest_pickup_slot = max(1, n_days * 48 - 10)
        pickup_slot = random.randint(0, latest_pickup_slot - 1)
        duration_hours = random.randint(1, max(1, min(96, n_days * 24 - pickup_slot // 2)))
        pickup = start + timedelta(minutes=30 * pickup_slot)
        ret = pickup + timedelta(hours=duration_hours)
        if ret > start + timedelta(days=n_days):
            ret = start + timedelta(days=n_days)
            duration_hours = max(1, int((ret - pickup).total_seconds() // 3600))
            ret = pickup + timedelta(hours=duration_hours)
        lines.append(
            f"{order_id},{level},{pickup_station},{return_station},"
            f"{pickup.strftime('%Y/%m/%d %H:%M')},{ret.strftime('%Y/%m/%d %H:%M')}"
        )
    lines.append("==========")

    lines.append("From,To,Moving time")
    for i in range(1, n_stations + 1):
        for j in range(1, n_stations + 1):
            lines.append(f"{i},{j},{move[i, j]}")
    lines.append("==========")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_move_matrix(n_stations: int) -> dict[tuple[int, int], int]:
    coords = {i: (random.random(), random.random()) for i in range(1, n_stations + 1)}
    move: dict[tuple[int, int], int] = {}
    for i in range(1, n_stations + 1):
        for j in range(1, n_stations + 1):
            if i == j:
                move[i, j] = 0
            elif (j, i) in move:
                move[i, j] = move[j, i]
            else:
                xi, yi = coords[i]
                xj, yj = coords[j]
                minutes = 30 * max(1, round((((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5) * 20))
                move[i, j] = minutes
    return move


def choose_stations(n_stations: int, flow: str) -> tuple[int, int]:
    if flow == "balanced":
        return random.randint(1, n_stations), random.randint(1, n_stations)
    split1 = max(1, n_stations // 4)
    split2 = max(split1 + 1, 3 * n_stations // 4)
    low = list(range(1, split1 + 1))
    mid = list(range(split1 + 1, split2 + 1))
    high = list(range(split2 + 1, n_stations + 1))
    pickup_group = random.choices([low, mid, high], weights=[0.6, 0.3, 0.1], k=1)[0]
    return_group = random.choices([low, mid, high], weights=[0.1, 0.3, 0.6], k=1)[0]
    return random.choice(pickup_group), random.choice(return_group)


SCENARIOS = {
    "small_balanced": dict(n_stations=10, n_cars=40, n_levels=3, n_orders=120, n_days=7, budget=8000, level_weights=[1, 1, 1], flow="balanced"),
    "low_level_heavy": dict(n_stations=20, n_cars=100, n_levels=4, n_orders=300, n_days=14, budget=25000, level_weights=[0.55, 0.25, 0.15, 0.05], flow="balanced"),
    "imbalanced_flow": dict(n_stations=30, n_cars=200, n_levels=5, n_orders=800, n_days=30, budget=80000, level_weights=[1, 1, 1, 1, 1], flow="imbalanced"),
    "large_dense": dict(n_stations=100, n_cars=1000, n_levels=10, n_orders=10000, n_days=100, budget=1000000, level_weights=[1] * 10, flow="imbalanced"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="generated_data")
    parser.add_argument("--per-scenario", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1142)
    args = parser.parse_args()
    random.seed(args.seed)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    for scenario, params in SCENARIOS.items():
        for rep in range(1, args.per_scenario + 1):
            path = out_dir / f"{scenario}_{rep:02d}.txt"
            write_instance(path, **params)
            print(path)


if __name__ == "__main__":
    main()

