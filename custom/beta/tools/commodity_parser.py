import json
import re
from beta.tools.utils import str_to_tuple, to_dict

class commodity_parser():

    def __init__(self):
        pass

    def parser(self, packet):
        
        name_list = []
        coms_dict = {}

        for commodity in packet:
            name = commodity["name"]
            name_list.append(name)
            coms_dict[name] = commodity
        
        return name_list, coms_dict

    def parse_node(self, commodity_name, commodities_dict):
        nodes = []
        src = self.parse_src(commodity_name, commodities_dict)
        dsts = self.parse_dsts(commodity_name, commodities_dict)

        if src:
            nodes.append(src)
        if dsts:
            nodes.extend(dsts)

        return nodes

    def parse_paths(self, commodity_name, commodities_dict):
        paths = []
        for path in commodities_dict[commodity_name]["paths"]:
            data = {}
            for link, bw in path.items():
                if '-' in link:
                    u, v = link.split('-')
                    data[(u, v)] = int(bw)  # 確保帶寬是數字
                else:
                    print(f"Warning: Invalid link format {link}")
                    continue  # 跳過錯誤的 link


            paths.append(data)
        
        return paths

    def parse_src(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["source"]

    def parse_dsts(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["destinations"]

    def parse_demand(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["total_demand"]

    def add_packet(self, commodity, packet = None):
        """ 先逐個 `commodity` 序列化，然後合併 """

        if not packet:
            packet = []
        
        packet.append(commodity)

        return packet
    
    def serialize_commodity(self, 
                            name, 
                            src=None, 
                            dsts=None, 
                            demand=None, 
                            paths=None):

        return {
        "name": name,
        "source": src if src else "unknown",  # 確保不為 None
        "destinations": dsts if isinstance(dsts, list) else [],  # 確保 dsts 為 list
        "total_demand": int(demand) if demand is not None else 0,  # 確保 demand 為 int
        "paths": to_dict(paths) if paths else []  # 確保 paths 正確格式
    }
