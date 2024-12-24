import json

class TopologyParser:
    def __init__(self, data = None):
        self.nodes = []
        self.links = []
        self.host_to_mac = {}
        self.mac_to_host = {}
        self.data = data

    def parse_data(self):
        """
        解析 JSON 数据，将其转换为所需格式。
        """
        # 提取 nodes
        self.nodes, self.mac_to_host, self.host_to_mac = self.parse_node(self.data)
        self.links = self.parse_link(self.data)


    def parse_node(self, data):
        
        nodes = []

        switchports = data["switchports"]
        nodes = list(switchports.keys())

        hosts = data["hosts"]
        m_to_h = {}
        h_to_m = {}
        for idx, mac in enumerate(hosts.keys(), start=1):
            m_to_h[mac] = f"h{idx}"
            h_to_m[f"h{idx}"] = mac
        
        combined_nodes = nodes + list(m_to_h.values())

        return combined_nodes, m_to_h, h_to_m
    
    def parse_link(self, data):
        
        links_list = []
        links = data["links"]

        for src, target in links.items():
            for dst, ports in target.items():
                links_list.append([src, dst])
        
        hosts = data["hosts"]
        for host_mac, context in hosts.items():
            host = self.mac_to_host[host_mac]
            sw = context["sw_id"]
            links_list.append([host, f'{sw}'])
            links_list.append([f'{sw}', host])

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
