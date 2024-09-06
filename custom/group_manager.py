import json
import os
import logging

class GroupManager:
    def __init__(self, json_file='multicast_groups.json', logger=None):
        self.group_cache = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_file = os.path.join(base_dir, json_file)
        self.logger = logger or logging.getLogger(__name__)

        # 初始化 IPv4 和 IPv6 群組
        self.groups_ipv4 = {}
        self.groups_ipv6 = {}

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

            self.groups_ipv4 = data.get("ipv4", {})
            self.groups_ipv6 = data.get("ipv6", {})

        self.logger.info(f"Loaded ipv4 groups: {self.groups_ipv4}")
        self.logger.info(f"Loaded ipv6 groups: {self.groups_ipv6}")

    def save_groups_to_json(self):
        """將當前的群組信息保存到 JSON 文件"""
        data = {
            "ipv4": self.groups_ipv4,
            "ipv6": self.groups_ipv6
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
            # 为每个端口创建一个桶
            bucket = parser.OFPBucket(actions=actions)
            buckets.append(bucket)

        # 创建多播组，并发送至交换机
        req = parser.OFPGroupMod(datapath=datapath, 
                                 command=ofproto.OFPFC_ADD,
                                 type_=ofproto.OFPGT_ALL, 
                                 group_id=group_id, 
                                 buckets=buckets)
        datapath.send_msg(req)

    def get_or_create_group(self, datapath, multicast_ip, ports):
        """獲取或創建群組"""
        if multicast_ip in self.group_cache:
            self.logger.info(f"Getting existing group for {multicast_ip}")
            group_id = self.group_cache[multicast_ip]
        else:
            self.logger.info(f"Creating new group for {multicast_ip}")
            group_id = hash(multicast_ip) % (2**32)
            self.add_group(datapath, group_id, ports)
            self.group_cache[multicast_ip] = group_id
        return group_id

    def add_multicast_member(self, multicast_ip, port, ipv6=False):
        """添加多播成員"""
        groups = self.groups_ipv6 if ipv6 else self.groups_ipv4
        if multicast_ip not in groups:
            groups[multicast_ip] = []
        if port not in groups[multicast_ip]:
            groups[multicast_ip].append(port)
            self.save_groups_to_json()

    def remove_multicast_member(self, multicast_ip, port, ipv6=False):
        """移除多播成員"""
        groups = self.groups_ipv6 if ipv6 else self.groups_ipv4
        if multicast_ip in groups and port in groups[multicast_ip]:
            groups[multicast_ip].remove(port)
            self.save_groups_to_json()

    def get_multicast_ports(self, multicast_ip, ipv6=False):
        """獲取多播端口列表"""
        groups = self.groups_ipv6 if ipv6 else self.groups_ipv4
        return groups.get(multicast_ip, [])
    
    def get_ipv4_groups(self):
        """返回所有 IPv4 群組"""
        return self.groups_ipv4
    
    def get_ipv6_groups(self):
        """返回所有 IPv6 群組"""
        return self.groups_ipv6
    
    def is_ipv4_in_groups(self, ipv4):
        """檢查 IPv4 地址是否在群組中"""
        return ipv4 in self.groups_ipv4
    
    def is_ipv6_in_groups(self, ipv6):
        """檢查 IPv6 地址是否在群組中"""
        return ipv6 in self.groups_ipv6
