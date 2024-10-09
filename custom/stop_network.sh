#!/bin/bash

# 停止所有 Ryu Controller 實例
echo "Stopping Ryu Controller..."
pkill -f ryu-manager

# 清理 Mininet（如果有殘留）
echo "Stopping Mininet..."
sudo mn -c