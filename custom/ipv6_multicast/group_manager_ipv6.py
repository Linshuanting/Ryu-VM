import json
import os
import logging

class GroupManager:
    def __init__(self, json_file='group.json', logger=None):
        self.group_cache = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_file = os.path.join(base_dir, json_file)
        self.logger = logger or logging.getLogger(__name__)

        # 初始化 switches 組態
        self.switches = {}

        # 嘗試從 JSON 文件加載現有群組
        if os.path.exists(self.json_file):
            self.logger.info("Loading group json file")
            self.load_groups_from_json()
        else:
            self.logger.info("JSON file not found, initializing empty group list")

    def load_groups_from_json(self):
        """從 JSON 文件中加載群組信息"""
        with open(self.json_file, 'r') as file:
            data = json.load(file)

            # 將 json switches 下的 key 改成 int，而不是 json 檔預設的 str
            # self.switches = data.get("switches", {})
            self.switches = {int(k): v for k, v in data.get("switches", {}).items()}

        self.logger.info(f"Loaded switch groups: {self.switches}")

    def save_groups_to_json(self):
        """將當前的群組信息保存到 JSON 文件"""
        data = {
            "switches": self.switches
        }
        with open(self.json_file, 'w') as file:
            json.dump(data, file, indent=4)
        
    def add_group(self, datapath, group_id, ports):
        """向交換機添加多播組"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        buckets = []

        for port in ports:
            actions = [parser.OFPActionOutput(port)]
            # 為每個端口創建一個桶
            bucket = parser.OFPBucket(actions=actions)
            buckets.append(bucket)

        # 創建多播組，並發送至交換機
        req = parser.OFPGroupMod(datapath=datapath, 
                                 command=ofproto.OFPFC_ADD,
                                 type_=ofproto.OFPGT_ALL, 
                                 group_id=group_id, 
                                 buckets=buckets)
        datapath.send_msg(req)

    def get_or_create_group(self, datapath, multicast_ip, ports, switch_id):
        """獲取或創建群組"""
        key = (switch_id, multicast_ip)
        if key in self.group_cache:
            self.logger.info(f"Getting existing group for {multicast_ip} on switch {switch_id}")
            group_id = self.group_cache[key]
        else:
            self.logger.info(f"Creating new group for {multicast_ip} on switch {switch_id}")
            group_id = hash(key) % (2**32)
            self.add_group(datapath, group_id, ports)
            self.group_cache[key] = group_id
        return group_id

    def add_multicast_member(self, switch_id, multicast_ip, port, ipv6=False):
        """添加多播成員"""
        if switch_id not in self.switches:
            self.switches[switch_id] = {"ipv4": {}, "ipv6": {}}

        groups = self.switches[switch_id]["ipv6"] if ipv6 else self.switches[switch_id]["ipv4"]

        if multicast_ip not in groups:
            groups[multicast_ip] = []
        if port not in groups[multicast_ip]:
            groups[multicast_ip].append(port)
            self.save_groups_to_json()

    def remove_multicast_member(self, switch_id, multicast_ip, port, ipv6=False):
        """移除多播成員"""
        if switch_id in self.switches:
            groups = self.switches[switch_id]["ipv6"] if ipv6 else self.switches[switch_id]["ipv4"]
            if multicast_ip in groups and port in groups[multicast_ip]:
                groups[multicast_ip].remove(port)
                self.save_groups_to_json()

    def get_multicast_ports(self, switch_id, multicast_ip, ipv6=False):
        """獲取多播端口列表"""
        if switch_id in self.switches:
            groups = self.switches[switch_id]["ipv6"] if ipv6 else self.switches[switch_id]["ipv4"]
            return groups.get(multicast_ip, [])
        return []

    def get_ipv4_groups(self, switch_id):
        """返回指定交換機的所有 IPv4 群組"""
        if switch_id in self.switches:
            return self.switches[switch_id]["ipv4"]
        return {}

    def get_ipv6_groups(self, switch_id):
        """返回指定交換機的所有 IPv6 群組"""
        if switch_id in self.switches:
            return self.switches[switch_id]["ipv6"]
        return {}

    def is_ipv4_in_groups(self, switch_id, ipv4):
        """檢查 IPv4 地址是否在指定交換機的群組中"""
        return ipv4 in self.get_ipv4_groups(switch_id)

    def is_ipv6_in_groups(self, switch_id, ipv6):
        """檢查 IPv6 地址是否在指定交換機的群組中"""
        return ipv6 in self.get_ipv6_groups(switch_id)
    
