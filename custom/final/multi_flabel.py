import json
import ipaddress
from typing import List, Dict, Optional

class MultiFLabelDB:
    def __init__(self, prefix_bits=8):
        # 初始化数据库
        self.commodity_to_group: Dict[str, int] = {}  # commodity 对应的 group id
        self.groups: Dict[int, MultiGroup] = {}  # group_id 对应的组
        self.group_id_counter = 1
        self.prefix_bits = prefix_bits
    
    def _get_group_by_commodity(self, commodity: str) -> Optional["MultiGroup"]:
        """
        根据 commodity 获取对应的组，如果不存在，抛出异常
        """
        if commodity not in self.commodity_to_group:
            raise ValueError(f"Commodity {commodity} 未分配组！")
        group_id = self.commodity_to_group[commodity]
        return self.groups[group_id]
    
    def create_group_for_commodity(self, commodity:str) -> int:
        
        if commodity in self.commodity_to_group:
            print(f"Commodity {commodity} 已分配到组 {self.commodity_to_group[commodity]}")
            return self.commodity_to_group[commodity]
        
        group_id = self.group_id_counter
        group = MultiGroup(group_id, 4)

        # 存储并返回
        self.commodity_to_group[commodity] = group_id
        self.groups[group_id] = group
        self.group_id_counter += 1

        return group_id
    
    def add_host_to_group(self, commodity: str, host: str):
        """
        为 commodity 对应的组添加主机
        """
        group = self._get_group_by_commodity(commodity)
        group.add_host(host)

    def assign_subgroup(self, commodity: str) -> tuple:
        group = self._get_group_by_commodity(commodity)
        return group.assign_subgroup_flabel()
    
    def get_all_subgroup(self, commodity: str):
        group = self._get_group_by_commodity(commodity)
        return group.get_all_subgroups()
    
    def print_all_groups(self):
        """
        打印所有组的信息
        """
        for group_id, group in self.groups.items():
            print(f"组 {group_id}, 組value {group.get_group_value()}, 組Mask {group.get_group_mask()}")
            print(f"  分配的内部 Flabel: {group.get_all_subgroups()}")
            print(f"  分配的主机: {group.get_all_hosts()}")


class MultiGroup:
    def __init__(self, group_id:int, match_bits:int):
        self.group_id = group_id
        self.assigned_flabel: set[(int, int)] = set() # flow label value & flow label mask
        self.counter = 1
        self.hosts: List[str] = []
        self.match_bits = match_bits
        self.base_flabel_value, self.base_flabel_mask = self.generate_ipv6_flabel(group_id, match_bits) 
        

    def assign_subgroup_flabel(self):
        """
        生成三段的 Flabel
        
        Example:
        Flow_Label_ID (4 bits) | Flow_SubGroup (4 bits) | Mask (12 bits)

        """
        total_bits = 20
        mask_bits = 20 - self.match_bits*2

        flabel_value = ((self.group_id << (total_bits-self.match_bits))|(self.counter << mask_bits)) & 0xFFFFF
        flabel_mask = 0xFFFFF & (~((1 << mask_bits)-1))

        self.assigned_flabel.add((flabel_value, flabel_mask))
        self.counter+=1

        return flabel_value, flabel_mask

    def generate_ipv6_flabel(self, group_id: int, match_bits: int) -> tuple:
        """
        生成符合 OpenFlow 匹配規則的 ipv6_flabel 值與掩碼。
        
        :param group_id: 分配的 group ID（用於 flow label 高位）
        :param match_bits: 需要匹配的高位 bits（其餘 bits 將被 mask）
        :return: (ipv6_flabel_value, ipv6_flabel_mask)
        """
        if not (0 <= match_bits <= 20):
            raise ValueError("IPv6 Flow Label 只能有 20 bits，match_bits 必須在 0 到 20 之間")

        total_bits = 20  # IPv6 Flow Label 總長度
        mask_bits = total_bits - match_bits  # 需要 mask 的位數

        # 計算匹配值（只保留高位 match_bits，其餘補 0）
        flabel_value = (group_id << mask_bits) & 0xFFFFF  # 只取 20 bits

        # 計算掩碼（匹配 match_bits，其餘 mask 為 0）
        flabel_mask = (0xFFFFF >> mask_bits) << mask_bits  # 產生相應 mask

        return flabel_value, flabel_mask
    
    def get_group_mask(self):
        return self.base_flabel_mask
    
    def get_group_value(self):
        return self.base_flabel_value
    
    def get_all_subgroups(self):
        """
        获取组内所有已分配的内部 Flabel value & mask
        """
        return list(self.assigned_flabel)

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
    