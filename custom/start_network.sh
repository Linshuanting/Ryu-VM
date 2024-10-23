#!/bin/bash

# 檢查參數
if [ $# -ne 2 ]; then
    echo "Usage: $0 <ryu_controller_path> <mininet_topology_path>"
    exit 1
fi

RYU_CONTROLLER_PATH=$1
MININET_TOPOLOGY_PATH=$2
PASSWORD='user'

# 啟動 Ryu Controller
echo "Starting Ryu Controller..."
ryu-manager $RYU_CONTROLLER_PATH &  # 將 Ryu Controller 在背景運行
RYU_PID=$!


# 設置 trap 在腳本結束或收到 SIGTSTP 信號時終止 Ryu Controller 和 Mininet
cleanup() {
    echo "Shutting down Ryu Controller..."
    kill $RYU_PID
    pkill -f "$MININET_TOPOLOGY_PATH"  # 終止 Mininet 的進程
    echo $PASSWORD | sudo -S mn -c
    echo "Mininet window closed."
}

trap cleanup EXIT  # 在腳本結束時執行
trap cleanup SIGTSTP  # 在收到 Ctrl+Z (SIGTSTP) 時執行

# 延遲以確保 Ryu Controller 完全啟動
sleep 1

# 啟動 Mininet，並等待該窗口的進程結束
echo "Starting Mininet with topology script $MININET_TOPOLOGY_PATH..."
gnome-terminal --wait -- bash -c "sudo python3 $MININET_TOPOLOGY_PATH; exit"