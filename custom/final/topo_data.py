from collections import defaultdict as ddict
from sortedcontainers import SortedList
import re

class Topology(dict):

    P_DOWN = None
    P_UP = 1

    def __init__(self):

        # 紀錄 switch 上的所有 ports
        self.switchports=ddict(dict)
        # 紀錄兩個 switch 之間的連接 
        self.links = ddict(dict)
        self.mac_to_port=ddict(dict)
        # 紀錄 switch mac_addres 對應的 switch_id, port
        self.mac_to_sw_id_port = ddict(dict)
        # 紀錄 host mac_address, host_ip, 以及其對應連接的 switch_id, switch_port
        self.hosts = ddict(dict)
        # 紀錄 switch datapath id 以及其對應的 datapath
        self.datapaths = {}
        # 紀錄 client 傳來的資料
        self.flow = {}

    def parser(self, data):
        pass

    def to_dict(self):
        # 将 defaultdict 递归地转换为标准 dict
        return {
            "switchports": self._defaultdict_to_dict(self.switchports),
            "links": self._defaultdict_to_dict(self.links),
            "mac_to_port": self._defaultdict_to_dict(self.mac_to_port),
            "mac_to_sw_id_port": self._defaultdict_to_dict(self.mac_to_sw_id_port),
            "hosts": self._defaultdict_to_dict(self.hosts)
        }

    def _defaultdict_to_dict(self, d):
        if isinstance(d, (ddict, dict)):
            return {k: self._defaultdict_to_dict(v) for k, v in d.items()}
        elif isinstance(d, (SortedList, list)):  
            return [self._defaultdict_to_dict(v) for v in d] 
        return d
    
    def set_flow(self, data):
        self.flow = data
    
    def get_flow(self):
        print("----- this is commodity flow -----")
        print(self.flow)
        return self.flow

    def set_datapath(self, dp):
        dp_id = dp.id
        self.datapaths[dp_id] = dp
    
    def get_datapath(self, dp_id):
        return self.datapaths[self.turn_to_key(dp_id)]

    def set_host(self, host_mac, host_ip, sw_id, sw_in_port):
        # 如果該 MAC 地址已存在，將新的 IP 地址添加到列表中
        if host_mac in self.hosts:
            # 檢查 IP 是否已經在列表中，如果沒有，則添加
            if host_ip not in self.hosts[host_mac]['ips']:
                self.hosts[host_mac]['ips'].add(host_ip)
        else:
            # 如果該 MAC 地址不存在，則創建新的條目
            self.hosts[host_mac] = {
                'ips': SortedList([host_ip]),  # 使用列表來存儲多個 IP
                'sw_id': sw_id,
                'sw_in_port': sw_in_port
            }

    def get_host(self, host_mac):
        if host_mac in self.hosts:
            return self.hosts[host_mac]
        return None
    
    def get_hosts(self):
        print("------ Get all hosts -------")
        for host_mac, host_info in self.hosts.items():  # host_info 是元組
            print(f"host mac: {host_mac}, host ips: {host_info['ips']}, switch id: {host_info['sw_id']}, switch port: {host_info['sw_in_port']}")

    def is_host(self, mac):
        if mac in self.hosts:
            return True
        return False
    
    def is_mac(self, s):
        return bool(re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", s))
    
    def is_ip_is_used(self, ip):
        for host_mac, host_info in self.hosts.items():
            for host_ip in host_info['ips']:
                if ip == host_ip:
                    return True
        return False
    
    def get_mac_from_ip(self, ip):
        for host_mac, host_info in self.hosts.items():
            for host_ip in host_info['ips']:
                if ip == host_ip:
                    return host_mac
        return None
    
    def get_ports_in_switch(self, dp):
        if dp in self.switchports:
            return [port for port in self.switchports[dp]]
        return []
    
    def set_switch_port_mac(self, mac, port, dp):
        self.mac_to_sw_id_port[mac]= (dp, port)
    
    def get_switch_port_mac(self, mac):
        pass

    def is_switch_mac(self, mac):
        return mac in self.mac_to_sw_id_port

    def set_port_in_switch(self, dp, port):
        self.switchports[dp][port]= Topology.P_UP

    def is_port_in_switch(self, dp, port):
        return dp in self.switchports and port in self.switchports[dp]

    def build_edge(self, src_id, src_port, dst_id, dst_port):
        self.links[src_id][dst_id] = src_port, dst_port

    def _is_link(self, src_id, dst_id):
        if src_id in self.links and dst_id in self.links[src_id]:
            return self.links[src_id][dst_id]
        elif src_id in self.hosts:
            return (-1, self.hosts[src_id]["sw_in_port"])
        elif dst_id in self.hosts:
            return (self.hosts[dst_id]["sw_in_port"], -1)
        return None
    
    def remove_edge(self, src_id, dst_id):
        if src_id in self.links and dst_id in self.links[src_id]:
            del self.links[src_id][dst_id]
        # 如果 links[src_id] 已經沒有其他鏈接，可以選擇刪除它
        if not self.links[src_id]:
            del self.links[src_id]

    def get_links(self):
        all_links = []
        for src_id, dsts in self.links.items():
            for dst_id, ports in dsts.items():
                # 端口信息是 (src_port, dst_port)
                src_port, dst_port = ports
                # 將鏈接信息添加到 all_links 列表
                all_links.append((src_id, src_port, dst_id, dst_port))
                print(f"src:{src_id}, dst:{dst_id}")
                print(f"src port:{src_port}, dst port:{dst_port}")
        return all_links
    
    def get_ports_from_link(self, u, v) -> tuple[int, int]:
        r, s = self.turn_to_key(u), self.turn_to_key(v)
        print(f"u:{r}, v:{s}, links:{self._is_link(r, s)}")
        return self._is_link(r, s)
    
    def turn_to_key(self, u):
        if self.is_mac(u):
            return u
        elif isinstance(u, str):
            return int(u)
        return u 
