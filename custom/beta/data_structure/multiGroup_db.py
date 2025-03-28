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

    def set_commodities(self, commodtiy_name, src, dsts, paths, bw):

        myCommodity = Commodity(commodtiy_name)
        myCommodity.set_commodity_data( 
            ipv6_address=self.set_ipv6(self.group_counter),
            src = src,
            dsts = dsts,
            paths = paths,
            bw=bw
        )
        myCommodity.set_dstport(self.set_dport(self.group_counter))

        self.commodities[commodtiy_name] = myCommodity
        self.group_counter+=1

    def set_ipv6(self, counter):
        ipv6_addr = f"{self.base_ipv6_addr}{counter:04x}" # e.g. ff38::1
        return ipv6_addr
    
    def set_dport(self, counter):
        base_port = 6000
        return counter+base_port
    
    def get_ipv6(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_ipv6_addr()
    
    def get_src(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_src()
    
    def get_dsts(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_dsts()
        
    def get_commodity_group_list(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_group_list()
        
    def get_commodity(self, name)-> "Commodity":
        if name in self.commodities:
            return self.commodities[name]
    
    def get_paths(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_paths()
    
    def get_bandwidth(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_bandwidth()
    
    def get_dst_port(self, commodity_name):
        if commodity_name in self.commodities:
            return self.commodities[commodity_name].get_dstport()

class Commodity:
    # TODO
    # modify dst_port

    def __init__(self, name):
        self.commodity_name = name
        self.ipv6_address = ""
        self.base_flabel = 0x80000
        self.src_host = []
        self.dst_hosts = []
        self.bandwidth = 0
        self.commodity_group_lists = []
        self.group_counter = 1
        self.dst_port = 0
    
    def set_commodity_data(self, ipv6_address, src, dsts, paths, bw):
        self.ipv6_address = ipv6_address
        self.src_host = src
        self.dst_hosts = dsts
        self.bandwidth = bw

        for path in paths:
            
            flabel, mask = self.set_flabel(self.group_counter)
            sport = self.set_sport(self.group_counter)
            
            commodity_group = _group(
                ipv6_addr=ipv6_address,
                flabel=flabel,
                flabel_mask=mask,
                path=path,
                sport=sport
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
        
        flabel_value = (counter << mask_bits) | self.base_flabel
        flabel_mask = 0xFFFFF & (~((1 << mask_bits)-1))

        return flabel_value, flabel_mask
    
    def set_sport(self, counter):

        base_port = 5000
        return base_port+counter
    
    def set_dstport(self, dport):
        self.dst_port = dport

    def get_ipv6_addr(self):
        return self.ipv6_address
    
    def get_src(self):
        return self.src_host
    
    def get_dsts(self):
        return self.dst_hosts
    
    def get_bandwidth(self):
        return self.bandwidth
    
    def get_dstport(self):
        return self.dst_port
    
    def get_group_list(self):
        return self.commodity_group_lists
    
    def get_paths(self):
        paths = []
        for info in self.commodity_group_lists:
            path = info.get_path()
            paths.append(path)
        
        return paths

class _group:

    def __init__(self, ipv6_addr=None, flabel = None, flabel_mask = None, path = None, sport=None):
        self.group_ipv6_address = ipv6_addr
        self.group_flabel = flabel
        self.group_flabel_mask = flabel_mask
        self.path = path
        self.sport = sport
        self.set_bandwidth(path)
    
    def set_ipv6(self, ipv6):
        self.group_ipv6_address = ipv6
    
    def set_flabel(self, flabel):
        self.group_flabel = flabel
    
    def set_flabel_mask(self, flabel_mask):
        self.group_flabel_mask = flabel_mask

    def set_bandwidth(self, path):
        self.bandwidth = 0
        for link, bw in path.items():
            self.bandwidth = bw
            return
        return 

    def set_path(self, path):
        self.path = path
    
    def set_sport(self, sport):
        self.sport = sport
    
    def get_ipv6(self):
        return self.group_ipv6_address
    
    def get_flabel(self):
        return self.group_flabel
    
    def get_flabel_mask(self):
        return self.group_flabel_mask
    
    def get_bandwidth(self):
        return self.bandwidth
    
    def get_path(self):
        return self.path

    def get_sport(self):
        return self.sport
    
    