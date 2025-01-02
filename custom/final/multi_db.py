import json
from typing import List, Dict, Optional

class MultiGroupDB:
    def __init__(self):
        # 初始化数据库
        self.group_to_hosts: Dict[str, List[str]] = {}  # 存储 multi group 对应的 hosts
        self.commodity_to_ip: Dict[str, str] = {}  # 存储 commodity 对应的 multi IP
        self.ip_counter = 1  # 用于动态分配 IPv6 multi group 的计数器
        self.base_ip = "ff38::"  # 基础 IPv6 多播地址

    def generate_new_ip(self) -> str:
        """
        动态生成新的 multi IP 地址
        """
        new_ip = f"{self.base_ip}{self.ip_counter}"
        self.ip_counter += 1
        return new_ip

    def add_multi_group(self, group_ip: str):
        if group_ip not in self.group_to_hosts:
            self.group_to_hosts[group_ip] = []
            print(f"multi group {group_ip} added.")
        else:
            print(f"multi group {group_ip} already exists.")

    def remove_multi_group(self, group_ip: str):
        if group_ip in self.group_to_hosts:
            del self.group_to_hosts[group_ip]
            print(f"multi group {group_ip} removed.")
        else:
            print(f"multi group {group_ip} does not exist.")

    def add_host_to_group(self, group_ip: str, host: str):
        if group_ip in self.group_to_hosts:
            if host not in self.group_to_hosts[group_ip]:
                self.group_to_hosts[group_ip].append(host)
                print(f"Host {host} added to group {group_ip}.")
            else:
                print(f"Host {host} is already in group {group_ip}.")
        else:
            print(f"multi group {group_ip} does not exist.")

    def assign_commodity_to_dynamic_ip(self, commodity: str) -> str:
        """
        动态为 commodity 分配一个新的 multi IP，并自动创建对应的组
        """
        if commodity in self.commodity_to_ip:
            print(f"Commodity {commodity} already assigned to IP {self.commodity_to_ip[commodity]}.")
            return self.commodity_to_ip[commodity]

        # 生成新 IP 并创建组
        new_ip = self.generate_new_ip()
        self.add_multi_group(new_ip)

        # 绑定 commodity 和 IP
        self.commodity_to_ip[commodity] = new_ip
        print(f"Commodity {commodity} assigned to new multi IP {new_ip}.")
        return new_ip

    def get_ip_for_commodity(self, commodity: str) -> Optional[str]:
        """
        查询指定 commodity 分配的 multi IP
        """
        return self.commodity_to_ip.get(commodity, None)

    def save_to_file(self, filename: str):
        data = {
            "group_to_hosts": self.group_to_hosts,
            "commodity_to_ip": self.commodity_to_ip,
            "ip_counter": self.ip_counter
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Database saved to {filename}.")

    def load_from_file(self, filename: str):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                self.group_to_hosts = data.get("group_to_hosts", {})
                self.commodity_to_ip = data.get("commodity_to_ip", {})
                self.ip_counter = data.get("ip_counter", 1)
            print(f"Database loaded from {filename}.")
        except FileNotFoundError:
            print(f"File {filename} not found. Starting with an empty database.")

    def print_db(self):
        print("Multi Group Database:")
        print("Group to Hosts:")
        for group, hosts in self.group_to_hosts.items():
            print(f"  Group {group}: {hosts}")
        print("Commodity to IP:")
        for commodity, ip in self.commodity_to_ip.items():
            print(f"  Commodity {commodity}: {ip}")
