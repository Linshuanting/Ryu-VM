import socket
import struct
import time
import random


# 創建一個 UDP IPv6 套接字
sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

# 設定目標地址和端口
destination_ip = "2001:db9::2"
port = 12345

def send_packet_with_flow_label(flow_label):
    # 設定 Flow Label 選項
    # IPv6 Flow Label 使用 IPv6 頭部的 4 個位元組，將流量標籤添加到傳送的資料包中
    flow_info = (6 << 28) | (flow_label << 8)  # 設定 IPv6 版本為 6 並添加 Flow Label

    # 組合封包
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_FLOWLABEL_MGR, struct.pack("I", flow_info))

    # 發送資料
    sock.sendto(b"Hello, world!", (destination_ip, port))
    print(f"Packet sent with Flow Label: {flow_label}")

# 定義固定的 10 個 Flow Label
# Flow label 最長可以有 20 bits
flow_labels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# 持續發送封包並每 0.5 秒更換 Flow Label
for i in range(4):
    # 隨機生成一個新的 Flow Label
    flow_label = flow_labels[i % len(flow_labels)]  
    print(f"Sending packet with Flow Label: {flow_label}")

    # 發送封包
    send_packet_with_flow_label(flow_label)

    # 每隔 0.5 秒
    time.sleep(0.5)
