import pandas as pd
import matplotlib.pyplot as plt
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
graph_dir = f"{current_dir}/graph"
# 假設你的資料已經存在 DataFrame 中，命名為 df
# 如果是從 CSV 讀取：df = pd.read_csv("your_data.csv")
df = pd.read_csv(f"{graph_dir}/runtime_comparison.csv")

# 將 compare_ratio > 1 的值設為 1
df['compare_ratio_clipped'] = df['compare_ratio'].apply(lambda x: min(x, 1))

# 圖1: 畫出 Mcfp_time 與 Myalg_time
plt.figure(figsize=(10, 5))
plt.plot(df['run'], df['mcfp_time'], label='mcfp_time', marker='o')
plt.plot(df['run'], df['myalg_time'], label='myalg_time', marker='x')
plt.xlabel("Run")
plt.ylabel("Time (s)")
plt.yscale("log")
plt.title("Mcfp vs Myalg Time")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(f"{graph_dir}/time_plot.png")  # 儲存為圖片
# plt.show()
plt.close()

df['Mcfp_time_ms'] = df['mcfp_time'] * 1000
df['Myalg_time_ms'] = df['myalg_time'] * 1000

# 1. Mcfp_time 單獨一張圖（毫秒）
plt.figure(figsize=(10, 4))
plt.plot(df['run'], df['Mcfp_time_ms'], label='Mcfp_time (ms)', marker='o', color='blue')
plt.xlabel("Run")
plt.ylabel("Time (ms)")
plt.yscale("log")
plt.title("Mcfp_time over Runs")
plt.grid(True)
plt.tight_layout()
plt.savefig(f"{graph_dir}/mcfp_time_plot.png")
plt.close()

# 2. Myalg_time 單獨一張圖（毫秒）
plt.figure(figsize=(10, 4))
plt.plot(df['run'], df['Myalg_time_ms'], label='Myalg_time (ms)', marker='x', color='orange')
plt.xlabel("Run")
plt.ylabel("Time (ms)")
plt.title("Myalg_time over Runs")
plt.grid(True)
plt.tight_layout()
plt.savefig(f"{graph_dir}/myalg_time_plot.png")
plt.close()

# 圖2: 畫出 Compare_ratio (clipped)
plt.figure(figsize=(10, 5))
plt.plot(df['run'], df['compare_ratio_clipped'], label='compare_ratio', marker='s')
plt.xlabel("Run")
plt.ylabel("Compare Ratio")
plt.title("Compare Ratio")
plt.ylim(0, 1.1)
plt.grid(True)
plt.tight_layout()
plt.savefig(f"{graph_dir}/compare_ratio_plot.png")  # 儲存為圖片
# plt.show()
plt.close()

