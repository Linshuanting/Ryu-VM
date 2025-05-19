import json
from ipaddress import IPv6Address
from typing import List, Dict, Optional

dport_num = 6001

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
        myCommodity.set_commodity_dport(self.set_dport(self.group_counter))

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
    
    def get_total_bandwidth(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_total_bandwidth()
    
    def get_bandwidth_list(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            return self.commodities[commodtiy_name].get_bandwidth_list()
    
    # 請求目前的 path 可以負載的 bandwidth，而非總共需要的 bandwidth
    def get_on_demand_bandwidth(self, commodtiy_name):
        if commodtiy_name in self.commodities:
            demand_bandwidth = 0
            for bw in self.commodities[commodtiy_name].get_bandwidth_list():
                demand_bandwidth += bw
            
            return demand_bandwidth
        return 0
    
    def get_dst_commodity_port(self, commodity_name):
        if commodity_name in self.commodities:
            return self.commodities[commodity_name].get_commodity_port()
    
    def get_src_port_list(self, commodity_name):
        if commodity_name in self.commodities:
            return self.commodities[commodity_name].get_srcports()

    def get_fl_port_dict(self, commodity_name):
        if commodity_name in self.commodities:
            return self.commodities[commodity_name].get_fl_p_dict()
    
    def get_tree_ports_list(self, commodity_name):
        if commodity_name in self.commodities:
            return self.commodities[commodity_name].get_trees_ports_list()

    def get_commodity_info(self, commodity_name):
        if commodity_name not in self.commodities:
            return    
        com = self.commodities[commodity_name]
        return {
            "commodity": commodity_name,
            "src": self.get_src(commodity_name),
            "dsts": self.get_dsts(commodity_name),
            "dst_ip": self.get_ipv6(commodity_name),
            "s_dport": self.get_src_port_list(commodity_name),
            "dport": self.get_dst_commodity_port(commodity_name),
            "bw": self.get_bandwidth_list(commodity_name)
        }
        

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
        self.commodity_dport = 0
    
    def set_commodity_data(self, ipv6_address, src, dsts, paths, bw):
        global dport_num
        self.ipv6_address = str(IPv6Address(ipv6_address))
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
                sport=sport,
                dport=dport_num
            )
            self.commodity_group_lists.append(commodity_group)
            dport_num+=1
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
    
    def set_commodity_dport(self, dport):
        self.commodity_dport = dport

    def get_ipv6_addr(self):
        return self.ipv6_address
    
    def get_src(self):
        return self.src_host
    
    def get_dsts(self):
        return self.dst_hosts
    
    def get_total_bandwidth(self):
        return self.bandwidth
    
    def get_bandwidth_list(self):
        bws = []
        for group in self.commodity_group_lists:
            bws.append(group.get_bandwidth())
        return bws 

    def get_commodity_port(self):
        return self.commodity_dport
    
    def get_trees_ports_list(self):
        ports = []
        for group in self.commodity_group_lists:
            ports.append(group.get_tree_dport())
        
        return ports
    
    def get_srcports(self):
        ports = []
        for group in self.commodity_group_lists:
            ports.append(group.get_sport())
        return ports
    
    def get_group_list(self):
        return self.commodity_group_lists
    
    def get_paths(self):
        paths = []
        for info in self.commodity_group_lists:
            path = info.get_path()
            paths.append(path)
        
        return paths
    
    def get_fl_p_dict(self):
        res = {}
        for group in self.commodity_group_lists:
            fl = group.get_flabel()
            port = group.get_tree_dport()
            res[fl] = port
        
        return res
class _group:

    def __init__(self, ipv6_addr=None, flabel = None, flabel_mask = None, path = None, sport=None, dport=None):
        self.group_ipv6_address = ipv6_addr
        self.group_flabel = flabel
        self.group_flabel_mask = flabel_mask
        self.path = path
        self.sport = sport
        self.dport = dport
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
    
    def set_tree_dport(self, dport):
        self.dport = dport
    
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
    
    def get_tree_dport(self):
        return self.dport
    
    