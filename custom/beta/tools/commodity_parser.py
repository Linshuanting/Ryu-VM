import json
import re
from beta.tools.utils import str_to_tuple

class commodity_parser():

    def __init__(self):
        pass

    def parser(self, commodities):
        
        name_list = []
        coms_dict = {}

        for commodity in commodities:
            name = commodity["name"]
            name_list.append(name)
            coms_dict[name] = commodity
        
        return name_list, coms_dict

    def parse_node(self, commodity_name, commodities_dict):
        node_list = []
        node_list.append(self.parse_src(commodity_name, commodities_dict))
        node_list.extend(self.parse_dsts(commodity_name, commodities_dict))
        return node_list

    def parse_paths(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["paths"]

    def parse_src(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["source"]

    def parse_dsts(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["destinations"]

    def parse_demand(self, commodity_name, commodities_dict):
        return commodities_dict[commodity_name]["total_demand"]

    def serialize(self, paths, commodities):

        result = []

        for commodity in commodities.items():
            name = commodity["name"]
            # 獲取對應路徑，若不存在使用空列表
            path = paths.get(name, [])

            combined_commodity = {
                "name": name,
                "source": commodity["source"],
                "destinations": commodity["destinations"],
                "total_demand": commodity["demand"],
                "paths": path
            }

            result.append(combined_commodity)

        return result