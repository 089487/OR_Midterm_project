import random
import os
import shutil
from datetime import datetime, timedelta

class IEDOProjectGenerator:
    def __init__(self, n_S=100, n_C=100):
        self.n_S = n_S
        self.n_C = n_C
        self.n_L = 10
        self.start_date = datetime(2023, 1, 1)

    def _get_level(self, mode, is_car=False):
        odds, evens = [1,3,5,7,9], [2,4,6,8,10]
        if mode == "8:2_skew":
            # 訂單 8(奇):2(偶) | 車輛 2(奇):8(偶)
            if is_car: return random.choice(odds) if random.random() < 0.2 else random.choice(evens)
            else: return random.choice(odds) if random.random() < 0.8 else random.choice(evens)
        return random.randint(1, 10)

    def _get_stations(self, mode):
        p_s, r_s = random.randint(1, self.n_S), random.randint(1, self.n_S)
        if mode == "odd_even":
            p_s = random.choice([s for s in range(1, self.n_S+1) if s % 2 == 0])
            r_s = random.choice([s for s in range(1, self.n_S+1) if s % 2 != 0])
        elif "hub" in mode:
            num_g = int(mode.split('_')[1][0])
            w = [1] * (self.n_S + 1)
            for g in range(num_g):
                for s in range(g*15+1, g*15+6): w[s] = 100 
            r_s = random.choices(range(0, self.n_S+1), weights=w)[0]
            if r_s == 0: r_s = 1
        return p_s, r_s

    def _get_times(self, n_D, mode):
        total_min = (n_D * 24 - 48) * 60 
        if mode == "weekend":
            days = list(range(n_D - 2))
            w = [5 if (d % 7) in [4, 5, 6] else 1 for d in days]
            m = (random.choices(days, weights=w)[0] * 24 * 60) + random.randint(0, 1439)
        elif "peak" in mode:
            num_p = int(mode.split('_')[1])
            centers = [total_min * (i+1)/(num_p+1) for i in range(num_p)]
            m = int(random.gauss(random.choice(centers), 180))
        else:
            m = random.randint(0, total_min)
        
        pickup = self.start_date + timedelta(minutes=(max(0, m) // 30) * 30)
        return pickup, pickup + timedelta(hours=random.randint(2, 48))

    def create_instance(self, config):
        # 1. 隨機決定天數 nD (7~100)
        nD = random.randint(7, 100)
        
        # 2. 根據 nD 計算預算 B
        b_mode = config['budget_mode']
        if b_mode == "0": B = 0
        elif b_mode == "30": B = 30 * nD
        elif b_mode == "300": B = 300 * nD
        else: B = 1000000 # "1M"
        
        n_K = int(self.n_C * config['ratio'])

        lines = [
            f"n_S,n_C,n_L,n_K,n_D,B",
            f"{self.n_S},{self.n_C},{self.n_L},{n_K},{nD},{B}",
            "==========",
            "Car ID,Level,Initial station"
        ]
        
        # Part 2: Cars (固定停在奇數站以配合 odd_even)
        odd_stations = [s for s in range(1, self.n_S+1) if s % 2 != 0]
        for i in range(1, self.n_C + 1):
            lvl = self._get_level(config['level_mode'], is_car=True)
            lines.append(f"{i},{lvl},{random.choice(odd_stations)}")
        lines.append("==========")
        
        # Part 3: Rates
        lines.append("Car level,Hour rate")
        lines += [f"{i},{200+i*100}" for i in range(1, 11)]
        lines.append("==========")
        
        # Part 4: Orders
        lines.append("Order ID,Level,Pick-up station,Return station,Pick-up time,Return time")
        for i in range(1, n_K + 1):
            lvl = self._get_level(config['level_mode'], is_car=False)
            ps, rs = self._get_stations(config['station_mode'])
            pt, rt = self._get_times(nD, config['time_mode'])
            lines.append(f"{i},{lvl},{ps},{rs},{pt.strftime('%Y/%m/%d %H:%M')},{rt.strftime('%Y/%m/%d %H:%M')}")
        lines.append("==========")
        
        # Part 5: Move Time (對稱矩陣)
        lines.append("From,To,Moving time")
        for s1 in range(1, self.n_S + 1):
            for s2 in range(1, self.n_S + 1):
                lines.append(f"{s1},{s2},{0 if s1==s2 else 90}")
        lines.append("==========")
        
        return "\n".join(lines)
    
# --- 定義配置矩陣 ---
CONFIGS = {
    # Base & 負荷測試 (Supply-Demand Ratio Tests)
    "S1":  {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "1M"},    # 基準情境
    "S2":  {"ratio": 0.1,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "1M"},    # 負荷度 (極低)
    "S3":  {"ratio": 0.333, "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "1M"},    # 負荷度 (低)
    "S4":  {"ratio": 3.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "1M"},    # 負荷度 (高)
    
    # 等級分布測試
    "S5":  {"ratio": 1.0,   "level_mode": "8:2_skew", "station_mode": "random",    "time_mode": "random",   "budget_mode": "1M"},    # 等級失配 (8:2)
    
    # 空間分布測試
    "S6":  {"ratio": 1.0,   "level_mode": "random",   "station_mode": "odd_even",  "time_mode": "random",   "budget_mode": "300"},   # 空間失配 (硬性)
    "S7":  {"ratio": 1.0,   "level_mode": "random",   "station_mode": "hub_1G",    "time_mode": "random",   "budget_mode": "300"},   # 樞紐黑洞 (1組)
    "S8":  {"ratio": 1.0,   "level_mode": "random",   "station_mode": "hub_2G",    "time_mode": "random",   "budget_mode": "300"},   # 樞紐黑洞 (2組)
    
    # 時間分布測試
    "S9":  {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "weekend",  "budget_mode": "1M"},    # 週期效應 (週末)
    "S10": {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "peak_1",   "budget_mode": "1M"},    # 爆發尖峰 (1峰)
    "S11": {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "peak_3",   "budget_mode": "1M"},    # 爆發尖峰 (3峰)
    
    # 財務預算測試
    "S12": {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "0"},     # 預算限制 (零)
    "S13": {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "30"},    # 預算限制 (緊)
    "S14": {"ratio": 1.0,   "level_mode": "random",   "station_mode": "random",    "time_mode": "random",   "budget_mode": "300"},   # 預算限制 (中)
}

if __name__ == "__main__":
    engine = IEDOProjectGenerator()
    root = "exp_instances"
    if os.path.exists(root): shutil.rmtree(root)
    os.makedirs(root)

    for sid, cfg in CONFIGS.items():
        folder = os.path.join(root, sid)
        os.makedirs(folder)
        print(f"Generating Scenario {sid}...")
        for i in range(1, 31):
            with open(os.path.join(folder, f"{sid}_inst_{i:02d}.txt"), "w") as f:
                f.write(engine.create_instance(cfg))
    print("Success: instances generated.")