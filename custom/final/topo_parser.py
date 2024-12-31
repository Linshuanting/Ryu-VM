import json
import re
from utils import str_to_tuple

class TopologyParser:
    def __init__(self, data = None):
        self.nodes = []
        self.links = []
        self.data = data

    def parse_data(self):
        """
        解析 JSON 数据，将其转换为所需格式。
        """
        # 提取 nodes
        self.nodes = self.parse_node(self.data)
        self.links = self.parse_link(self.data)

    def parse_node(self, data):
        
        nodes = set()

        links = data["links"]
        for link in links.keys():
            u, v = str_to_tuple(link)
            nodes.add(u)
            nodes.add(v)
        
        return list(nodes)
    
    def parse_link(self, data):
        
        links_list = []
        links = data["links"]

        for link in links.keys():
            [u, v] = str_to_tuple(link)
            links_list.append([u, v])

        return links_list

    def set_data(self, data):
        self.data = data

    def get_nodes(self):
        return self.nodes

    def get_links(self):
        return self.links
    
    def run(self):
        self.parse_data()

    def to_dict(self):
        """
        将数据转换为标准字典格式。
        """
        return {
            "nodes": self.nodes,
            "links": self.links
        }
    
    def print_parse_data(self):

        print("-- Nodes --")
        print(self.nodes)
        print("-- Links --")
        print(self.links)

    def serialize(self, data):
        pass
