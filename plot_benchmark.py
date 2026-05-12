import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

ip_log = pd.read_csv('data/exp_instances/ip_solver_run_log.csv')
ip_log['instance_name'] = ip_log['instance'].apply(lambda x: os.path.basename(x))
ip_profit_map = dict(zip(ip_log['instance_name'], ip_log['profit']))

algo1_wins, algo5_wins, ties = {}, {}, {}
algo1_avg_gaps, algo5_avg_gaps = {}, {}

scenarios = []

for s in range(1, 15):
    scenario = f"S{s}"
    csv_file = f"data/exp_instances/{scenario}/benchmark_results.csv"
    if not os.path.exists(csv_file):
        continue
    
    df = pd.read_csv(csv_file)
    
    a1_win, a5_win, tie = 0, 0, 0
    a1_gaps, a5_gaps = [], []
    
    for instance in df['instance'].unique():
        sub_df = df[df['instance'] == instance]
        if 'algo1' not in sub_df['algorithm'].values or 'algo5' not in sub_df['algorithm'].values:
            continue
            
        a1_m = sub_df[sub_df['algorithm'] == 'algo1'].iloc[0]
        a5_m = sub_df[sub_df['algorithm'] == 'algo5'].iloc[0]
        
        # profit check
        if a1_m['profit'] > a5_m['profit']:
            a1_win += 1
        elif a5_m['profit'] > a1_m['profit']:
            a5_win += 1
        else:
            if a1_m['moving_time'] < a5_m['moving_time']:
                a1_win += 1
            elif a5_m['moving_time'] < a1_m['moving_time']:
                a5_win += 1
            else:
                tie += 1
                
        # Gap check
        if instance in ip_profit_map:
            ip_profit = ip_profit_map[instance]
            a1_gap = (ip_profit - a1_m['profit']) / abs(ip_profit)
            a5_gap = (ip_profit - a5_m['profit']) / abs(ip_profit)
            
            if a1_gap < -1e-5 or a5_gap < -1e-5:
                print(f"ALERT ERROR: Optimal gap < 0 at {instance}! IP: {ip_profit}, A1:{a1_m['profit']} A5:{a5_m['profit']}")
                
            a1_gaps.append(max(0, a1_gap))
            a5_gaps.append(max(0, a5_gap))
            
    scenarios.append(scenario)
    algo1_wins[scenario] = a1_win
    algo5_wins[scenario] = a5_win
    ties[scenario] = tie
    
    algo1_avg_gaps[scenario] = np.mean(a1_gaps) if a1_gaps else 0
    algo5_avg_gaps[scenario] = np.mean(a5_gaps) if a5_gaps else 0

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

x = np.arange(len(scenarios))
width = 0.25

# Plot 1: Wins
ax1.bar(x - width, [algo1_wins[s] for s in scenarios], width, label='algo1 win')
ax1.bar(x, [algo5_wins[s] for s in scenarios], width, label='algo5 win')
ax1.bar(x + width, [ties[s] for s in scenarios], width, label='tie')

ax1.set_ylabel('Count')
ax1.set_title('Wins by Scenario (Profit priority, tie-breaker Moving Time)')
ax1.set_xticks(x)
ax1.set_xticklabels(scenarios)
ax1.legend()

# Plot 2: Gaps
ax2.plot(x, [algo1_avg_gaps[s]*100 for s in scenarios], marker='o', label='algo1 avg gap %')
ax2.plot(x, [algo5_avg_gaps[s]*100 for s in scenarios], marker='x', label='algo5 avg gap %')

ax2.set_ylabel('Average Optimal Gap (%)')
ax2.set_title('Average Optimal Gap by Scenario')
ax2.set_xticks(x)
ax2.set_xticklabels(scenarios)
ax2.legend()
ax2.grid(True, linestyle='--', alpha=0.6)

plt.tight_layout()
plt.savefig('benchmark_summary.png')
print("Saved benchmark_summary.png")

