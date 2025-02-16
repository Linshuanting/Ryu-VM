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
ryu-manager $RYU_CONTROLLER_PATH &  # 在後台運行 Ryu
RYU_PID=$!

# 設置 trap 在腳本結束時終止 Ryu Controller
cleanup() {
    echo "Shutting down Ryu Controller..."
    kill $RYU_PID
    echo $PASSWORD | sudo -S mn -c
    echo "Mininet window closed."
}

# 讓 `trap cleanup EXIT` 只在 Mininet 真的關閉時執行
trap 'if ! pgrep -f "python3 $MININET_TOPOLOGY_PATH"; then cleanup; fi' EXIT

# 等待 Ryu Controller 啟動
sleep 1

# 啟動 Mininet
echo "Starting Mininet with topology script $MININET_TOPOLOGY_PATH..."
gnome-terminal -- bash -c "sudo -E python3 $MININET_TOPOLOGY_PATH; exec bash" 