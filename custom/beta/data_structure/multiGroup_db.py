import json
import ipaddress
from typing import List, Dict, Optional


class MultiGroupDB:

    # TODO
    # 多播 IP 自動設置
    # commodity 裡面再分組
    # 紀錄 commodity 內部 host src, dst

    def __init__(self, base_ipv6_addr = "ff38::"):
        self.commodities = {}
        self.group_counter = 1
        self.base_ipv6_addr = base_ipv6_addr

    def set_commodities(self, commodtiy_name, src, dsts, commodity):

        myCommodity = _commodity(commodtiy_name)
        myCommodity.set_commodity_data( 
            ipv6_address=self.set_ipv6(self.group_counter),
            src = src,
            dsts = dsts,
            commodity=commodity
        )

        self.commodities[commodtiy_name] = myCommodity
        self.group_counter+=1

    def set_ipv6(self, counter):
        ipv6_addr = f"{self.base_ipv6_addr}{counter:04x}" # e.g. ff38::1
        return ipv6_addr
    
    def get_ipv6(self, commodity):
        if commodity in self.commodities:
            return self.commodities[commodity].get_ipv6_addr()
    
    def get_src(self, commodity):
        if commodity in self.commodities:
            return self.commodities[commodity].get_src()
    
    def get_dsts(self, commodity):
        if commodity in self.commodities:
            return self.commodities[commodity].get_dsts()
        
    def get_commodity_group_list(self, commodtiy):
        if commodtiy in self.commodities:
            return self.commodities[commodtiy].get_group_list()
    

class _commodity:
    def __init__(self, name):
        self.commodity_name = name
        self.ipv6_address = ""
        self.base_flabel = 0x80000
        self.src_host = []
        self.dst_hosts = []
        self.commodity_group_lists = []
        self.group_counter = 0
    
    
    def set_commodity_data(self, ipv6_address, src, dsts, commodity):
        self.ipv6_address = ipv6_address
        self.src_host = src
        self.dst_hosts = dsts

        for info in commodity:
            
            flabel, mask = self.set_flabel(self.group_counter)
            bandwidth = info['bandwidth']
            
            commodity_group = _group(
                ipv6_addr=ipv6_address,
                flabel=flabel,
                flabel_mask=mask,
                bandwidth=bandwidth
            )
            self.commodity_group_lists.append(commodity_group)
            self.group_counter += 1
    
    def set_flabel(self, counter):
        """
        生成兩段的 Flabel，使用 counter 來代表 subgroup 的序號
        
        Example:
        Flow Start (1 bits) | Flow_SubGroup (7 bits) | Mask (12 bits)

        """
        total_bits = 20
        mask_bits = 12
        
        flabel_value = (counter << mask_bits) & self.base_flabel
        flabel_mask = 0xFFFFF & (~((1 << mask_bits)-1))

        return flabel_value, flabel_mask

    def get_ipv6_addr(self):
        return self.ipv6_address
    
    def get_src(self):
        return self.src_host
    
    def get_dsts(self):
        return self.dst_hosts
    
    def get_group_list(self):
        return self.commodity_group_lists

class _group:

    def __init__(self, ipv6_addr=None, flabel = None, flabel_mask = None,bandwidth = 0):
        self.group_ipv6_address = ipv6_addr
        self.group_flabel = flabel
        self.group_flabel_mask = flabel_mask
        self.bandwidth = bandwidth
    
    def set_ipv6(self, ipv6):
        self.group_ipv6_address = ipv6
    
    def set_flabel(self, flabel):
        self.group_flabel = flabel
    
    def set_flabel_mask(self, flabel_mask):
        self.group_flabel_mask = flabel_mask

    def set_bandwidth(self, bw):
        self.bandwidth = bw
    
    def get_ipv6(self):
        return self.group_ipv6_address
    
    def get_flabel(self):
        return self.group_flabel
    
    def get_flabel_mask(self):
        return self.group_flabel_mask
    
    def get_bandwidth(self):
        return self.bandwidth
    