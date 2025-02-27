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
        group_ip = f"ff38::{group_id:04x}"  # e.g. ff38:1::

        group = MultiGroup(group_id, group_ip)

        self.groups[group_id] = group
        self.commodity_to_group[commodity] = group_id
        print(f"为 commodity {commodity} 创建组 {group_id}, Group IP:{group_ip}")

        self.group_id_counter += 1
        return group_id

    def add_host_to_group(self, commodity: str, host: str):
        """
        为 commodity 对应的组添加主机
        """
        group = self._get_group_by_commodity(commodity)
        group.add_host(host)
    
    def add_host_to_group(self, commodity: str, 
                          src_host:str=None, 
                          dst_host:str=None,
                          dst_hosts:list=None):
        group = self._get_group_by_commodity(commodity)
        if src_host is not None:
            group.add_src(src_host)
        if dst_host is not None:
            group.add_dst(dst_host=dst_host)
        if dst_hosts is not None:
            group.add_dst(dst_hosts=dst_hosts)
    
    def get_src_host_from_commodity(self, commodity: str):
        group = self._get_group_by_commodity(commodity)
        return group.get_src_host()
    
    def get_dst_hosts_from_commodity(self, commodity: str):
        group = self._get_group_by_commodity(commodity)
        return group.get_dst_hosts()

    def print_all_groups(self):
        """
        打印所有组的信息
        """
        for group_id, group in self.groups.items():
            print(f"组 {group_id} (IP: {group.group_ipv6}):")
            print(f"  分配的主机: {group.get_all_hosts()}")

    def get_commodity_ip(self, commodity:str):
        group_id = self.commodity_to_group[commodity]
        return f"ff38::{group_id:04x}"

class MultiGroup:
    def __init__(self, group_id: int, group_ip: ipaddress.IPv6Network):
        self.group_id = group_id
        self.group_ipv6 = group_ip  # e.g., ff38::0001
        self.hosts: List[str] = []  # 存储组内的主机
        self.src_host = None
        self.dst_hosts = []

    def add_host(self, host: str):
        """
        为组添加主机
        """
        if host not in self.hosts:
            self.hosts.append(host)
    
    def add_src(self, src_host: str):
        if self.src_host is None:
            self.src_host = src_host
            self.hosts.append(src_host)
        else:
            print(f"the src host:{self.src_host} is exist in Group ID:{self.group_id}")

    def add_dst(self, dst_host:str=None, dst_hosts:list=None):
        if dst_host is not None:
            self.dst_hosts.append(dst_host)
            self.hosts.append(dst_host)
        elif dst_hosts is not None:
            self.dst_hosts.extend(dst_hosts)
            self.hosts.extend(dst_hosts)
        else:
            print(f"the dst host is None in Group ID:{self.group_id}")

    def get_all_hosts(self) -> List[str]:
        """
        获取组内的所有主机
        """
        return self.hosts
    
    def get_src_host(self):
        return self.src_host
    
    def get_dst_hosts(self):
        return self.dst_hosts
