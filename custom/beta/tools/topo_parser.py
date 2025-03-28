import json
import re
from custom.beta.tools.utils import str_to_tuple

class TopologyParser:

    SINGLE_IP_STARTWITH = '2001'
    
    def __init__(self, data = None):
        self.nodes = []
        self.links = []
        self.data: dict = data

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
    
    def get_ip_from_host(self, host):

        for ip in self.data[host]['IPs']:
            if ip.startswith(self.SINGLE_IP_STARTWITH):
                return ip
        
        print(f"the host:{host}, not have single ipv6 startswith {self.SINGLE_IP_STARTWITH}")
        return None
    
    def get_single_ip_from_all_hosts(self) -> dict:

        hosts = {}
        for host, data in self.data.items():
            ips = data['IPs']
            for ip in ips:
                if ip.startswith(self.SINGLE_IP_STARTWITH):
                    hosts[host] = ip
        
        return hosts


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
