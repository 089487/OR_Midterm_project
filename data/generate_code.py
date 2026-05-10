import random
import os
import shutil
from datetime import datetime, timedelta

class IEDOFinalInstanceGenerator:
    def __init__(self, n_S=100, n_C=500, n_D=14):
        self.n_S = n_S
        self.n_C = n_C
        self.n_L = 10
        self.n_D = n_D
        self.start_date = datetime(2023, 1, 1)

    # --- 因子 1: 等級 (Level) ---
    def _get_level(self, mode, is_car=False):
        odds = [1, 3, 5, 7, 9]
        evens = [2, 4, 6, 8, 10]
        if mode == "8:2_skew":
            # 模擬「等級失配」壓力：訂單要奇數，但車子給偶數
            if is_car: # 車輛 2(奇):8(偶)
                return random.choice(odds) if random.random() < 0.2 else random.choice(evens)
            else:      # 訂單 8(奇):2(偶)
                return random.choice(odds) if random.random() < 0.8 else random.choice(evens)
        return random.randint(1, 10)

    # --- 因子 2: 站點 (Station) ---
    def _get_stations(self, mode):
        # 預設隨機分布
        p_s = random.randint(1, self.n_S)
        r_s = random.randint(1, self.n_S)
        
        if mode == "odd_even":
            # 硬性失配：車初始在奇數(由part2決定)，訂單從偶數去，奇數回
            p_s = random.choice([s for s in range(1, self.n_S+1) if s % 2 == 0])
            r_s = random.choice([s for s in range(1, self.n_S+1) if s % 2 != 0])
        elif mode.startswith("hub"):
            # 樞紐效應：還車會集中在某些區域
            num_groups = int(mode.split('_')[1][0])
            weights = [1] * (self.n_S + 1)
            for g in range(num_groups):
                start = (g * 20) + 1 
                for s in range(start, start + 5): weights[s] = 50 
            r_s = random.choices(range(0, self.n_S+1), weights=weights)[0]
            if r_s == 0: r_s = 1
        return p_s, r_s

    # --- 因子 3: 時間 (Time) ---
    def _get_times(self, mode):
        total_min = (self.n_D * 24 - 48) * 60 # 預留最後兩天洗車回港
        if mode == "weekend":
            days = list(range(self.n_D - 2))
            # 週末權重 5 倍
            weights = [5 if (d % 7) in [4, 5, 6] else 1 for d in days] 
            day = random.choices(days, weights=weights)[0]
            m = (day * 24 * 60) + random.randint(0, 1439)
        elif mode.startswith("peak"):
            # 爆發性尖峰 (Normal Distribution)
            num_p = int(mode.split('_')[1])
            centers = [total_min * (i+1)/(num_p+1) for i in range(num_p)]
            m = int(random.gauss(random.choice(centers), 120)) # 2hr 標準差
        else:
            m = random.randint(0, total_min)
        
        pickup = self.start_date + timedelta(minutes=(max(0, m) // 30) * 30)
        return pickup, pickup + timedelta(hours=random.randint(2, 48))

    # --- 核心：建立單一測資內容 ---
    def build_instance_content(self, config):
        n_K = int(self.n_C * config['ratio'])
        B = config['budget']
        
        content = []
        # Part 1: Global
        content += ["n_S,n_C,n_L,n_K,n_D,B", f"{self.n_S},{self.n_C},10,{n_K},{self.n_D},{B}", "=========="]
        
        # Part 2: Cars (固定讓初始車輛停在奇數站以配合 odd_even 測試)
        content += ["Car ID,Level,Initial station"]
        odd_stations = [s for s in range(1, self.n_S+1) if s % 2 != 0]
        for i in range(1, self.n_C + 1):
            lvl = self._get_level(config['level'], is_car=True)
            content.append(f"{i},{lvl},{random.choice(odd_stations)}")
        content += ["=========="]
        
        # Part 3: Rates
        content += ["Car level,Hour rate"] + [f"{i},{200+i*100}" for i in range(1,11)] + ["=========="]
        
        # Part 4: Orders
        content += ["Order ID,Level,Pick-up station,Return station,Pick-up time,Return time"]
        for i in range(1, n_K + 1):
            lvl = self._get_level(config['level'], is_car=False)
            ps, rs = self._get_stations(config['station'])
            pt, rt = self._get_times(config['time'])
            content.append(f"{i},{lvl},{ps},{rs},{pt.strftime('%Y/%m/%d %H:%M')},{rt.strftime('%Y/%m/%d %H:%M')}")
        content += ["=========="]
        
        # Part 5: Move Time (對稱矩陣)
        content += ["From,To,Moving time"]
        for s1 in range(1, self.n_S + 1):
            for s2 in range(1, self.n_S + 1):
                content.append(f"{s1},{s2},{0 if s1==s2 else 90}")
        content += ["=========="]
        
        return "\n".join(content)

# --- 25 個 Scenarios 的詳細配置矩陣 ---
SCENARIO_DATABASE = {
    # 格式: ID: {供需比, 等級模式, 站點模式, 時間模式, 預算}
    "S01": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "random",  "budget": 1000000},
    "S02": {"ratio": 0.1,  "level": "random",   "station": "random",   "time": "random",  "budget": 1000000},
    "S03": {"ratio": 0.33, "level": "random",   "station": "random",   "time": "random",  "budget": 1000000},
    "S04": {"ratio": 3.0,  "level": "random",   "station": "random",   "time": "random",  "budget": 1000000},
    "S05": {"ratio": 1.0,  "level": "8:2_skew", "station": "random",   "time": "random",  "budget": 1000000},
    "S06": {"ratio": 1.0,  "level": "random",   "station": "odd_even", "time": "random",  "budget": 1000000},
    "S07": {"ratio": 1.0,  "level": "random",   "station": "odd_even", "time": "random",  "budget": 300000},
    "S08": {"ratio": 1.0,  "level": "random",   "station": "hub_1G",   "time": "random",  "budget": 300000},
    "S09": {"ratio": 1.0,  "level": "random",   "station": "hub_2G",   "time": "random",  "budget": 300000},
    "S10": {"ratio": 1.0,  "level": "random",   "station": "hub_3G",   "time": "random",  "budget": 1000000},
    "S11": {"ratio": 1.0,  "level": "random",   "station": "hub_3G",   "time": "random",  "budget": 300000},
    "S12": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "weekend", "budget": 1000000},
    "S13": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "peak_1",  "budget": 1000000},
    "S14": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "peak_3",  "budget": 1000000},
    "S15": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "random",  "budget": 0},
    "S16": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "random",  "budget": 30000},
    "S17": {"ratio": 1.0,  "level": "random",   "station": "random",   "time": "random",  "budget": 300000},
    "S18": {"ratio": 3.0,  "level": "8:2_skew", "station": "odd_even", "time": "weekend", "budget": 300000},
    "S19": {"ratio": 3.0,  "level": "8:2_skew", "station": "odd_even", "time": "weekend", "budget": 30000},
    "S20": {"ratio": 3.0,  "level": "8:2_skew", "station": "odd_even", "time": "weekend", "budget": 1000000},
    "S21": {"ratio": 3.0,  "level": "8:2_skew", "station": "hub_3G",   "time": "weekend", "budget": 30000},
    "S22": {"ratio": 3.0,  "level": "8:2_skew", "station": "hub_3G",   "time": "weekend", "budget": 300000},
    "S23": {"ratio": 3.0,  "level": "8:2_skew", "station": "hub_3G",   "time": "weekend", "budget": 1000000},
    "S24": {"ratio": 10.0, "level": "8:2_skew", "station": "odd_even", "time": "weekend", "budget": 30000},
    "S25": {"ratio": 10.0, "level": "8:2_skew", "station": "hub_3G",   "time": "weekend", "budget": 30000},
}

def main():
    generator = IEDOFinalInstanceGenerator()
    instances_per_scenario = 30 # 這是你要求的統計樣本數
    base_folder = "Experiment_Data"

    if os.path.exists(base_folder):
        shutil.rmtree(base_folder) # 每次執行清空舊資料，避免混亂
    
    os.makedirs(base_folder)

    for sid, config in SCENARIO_DATABASE.items():
        # 為每個 Scenario 建立專屬資料夾
        scenario_path = os.path.join(base_folder, sid)
        os.makedirs(scenario_path)
        
        print(f"正在生成 {sid} 的測資檔案...")
        
        for i in range(1, instances_per_scenario + 1):
            content = generator.build_instance_content(config)
            filename = f"{sid}_inst_{i:02d}.txt"
            with open(os.path.join(scenario_path, filename), "w", encoding="utf-8") as f:
                f.write(content)

    print(f"\n✅ 生成完畢！所有測資已存放在 '{base_folder}' 資料夾下。")

if __name__ == "__main__":
    main()