import json
import ipaddress
from typing import List, Dict, Optional


class MultiGroupDB:
    def __init__(self):
        # 初始化数据库
        self.commodity_to_group: Dict[str, int] = {}  # commodity 对应的 group id
        self.groups: Dict[int, MultiGroup] = {}  # group_id 对应的组
        self.group_id_counter = 1

    def _get_group_by_commodity(self, commodity: str) -> Optional["MultiGroup"]:
        """
        根据 commodity 获取对应的组，如果不存在，抛出异常
        """
        if commodity not in self.commodity_to_group:
            raise ValueError(f"Commodity {commodity} 未分配组！")
        group_id = self.commodity_to_group[commodity]
        return self.groups[group_id]

    def create_group_for_commodity(self, commodity: str) -> int:
        """
        为 commodity 创建一个新的多播组
        """
        if commodity in self.commodity_to_group:
            print(f"Commodity {commodity} 已分配到组 {self.commodity_to_group[commodity]}")
            return self.commodity_to_group[commodity]

        # 分配新的 Multicast Group
        group_id = self.group_id_counter
        group_prefix = f"ff38:{group_id:04x}::"  # e.g., `ff38::0001`

        # 确保主机位清零，并使用 /112 掩码
        network_prefix = ipaddress.IPv6Network(f"{group_prefix}/112", strict=False)

        group = MultiGroup(group_id, network_prefix)

        self.groups[group_id] = group
        self.commodity_to_group[commodity] = group_id
        print(f"为 commodity {commodity} 创建组 {group_id}, 前缀 {group_prefix}/112")

        self.group_id_counter += 1
        return group_id

    def add_host_to_group(self, commodity: str, host: str):
        """
        为 commodity 对应的组添加主机
        """
        group = self._get_group_by_commodity(commodity)
        group.add_host(host)

    def get_prefix_for_commodity(self, commodity: str) -> ipaddress.IPv6Network:
        """
        获取 commodity 对应组的前缀 IP
        """
        group = self._get_group_by_commodity(commodity)
        return group.get_prefix()

    def assign_internal_ip(self, commodity: str) -> str:
        """
        为指定 commodity 的组分配内部 IP
        """
        group = self._get_group_by_commodity(commodity)
        return group.assign_internal_ip()

    def get_all_internal_ips(self, commodity: str) -> List[ipaddress.IPv6Address]:
        """
        获取指定 commodity 的所有内部 IP
        """
        group = self._get_group_by_commodity(commodity)
        return group.get_all_internal_ips()

    def print_all_groups(self):
        """
        打印所有组的信息
        """
        for group_id, group in self.groups.items():
            print(f"组 {group_id} (前缀: {group.base_ipv6_prefix}):")
            print(f"  分配的内部 IP: {group.get_all_internal_ips()}")
            print(f"  分配的主机: {group.get_all_hosts()}")


class MultiGroup:
    def __init__(self, group_id: int, base_ipv6_prefix: ipaddress.IPv6Network):
        self.group_id = group_id
        self.base_ipv6_prefix = base_ipv6_prefix  # e.g., ff38::0001/112
        self.assigned_ips: set[ipaddress.IPv6Address] = set()
        self.counter = 1  # 用于生成内部 IP 的计数器
        self.hosts: List[str] = []  # 存储组内的主机

    def assign_internal_ip(self) -> str:
        """
        为组内分配唯一的内部 IP（最后16位）
        """
        if self.counter > 0xFFFF:
            raise ValueError("No more internal IPs available in this group!")

        # 使用 ipaddress 模块生成新 IP
        new_ip = self.base_ipv6_prefix.network_address + self.counter
        if new_ip in self.assigned_ips:
            raise ValueError(f"Internal IP {new_ip} conflict in group!")

        self.assigned_ips.add(new_ip)
        self.counter += 1
        return str(new_ip)

    def get_all_internal_ips(self) -> List[ipaddress.IPv6Address]:
        """
        获取组内所有已分配的内部 IP
        """
        return list(self.assigned_ips)

    def get_prefix(self) -> ipaddress.IPv6Network:
        """
        获取组的前缀
        """
        return self.base_ipv6_prefix

    def add_host(self, host: str):
        """
        为组添加主机
        """
        if host not in self.hosts:
            self.hosts.append(host)

    def get_all_hosts(self) -> List[str]:
        """
        获取组内的所有主机
        """
        return self.hosts
