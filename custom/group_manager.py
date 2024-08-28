import json
import os

class GroupManager:
    def __init__(self, json_file='multicast_groups.json'):
        self.group_cache = {}
        self.json_file = json_file
        if os.path.exists(json_file):
            self.load_groups_from_json()
        else:
            self.groups = {}

    def load_groups_from_json(self):
        with open(self.json_file, 'r') as file:
            self.groups = json.load(file)

    def save_groups_to_json(self):
        with open(self.json_file, 'w') as file:
            json.dump(self.groups, file, indent=4)

    def add_group(self, datapath, group_id, ports):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        buckets = []

        for port in ports:
            actions = [parser.OFPActionOutput(port)]
            buckets.append(parser.OFPBucket(actions=actions))

        req = parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,
                                 ofproto.OFPGT_ALL, group_id, buckets)
        datapath.send_msg(req)

    def get_or_create_group(self, datapath, multicast_ip, ports):
        if multicast_ip in self.group_cache:
            group_id = self.group_cache[multicast_ip]
        else:
            group_id = hash(multicast_ip) % (2**32)
            self.add_group(datapath, group_id, ports)
            self.group_cache[multicast_ip] = group_id
        return group_id

    def add_multicast_member(self, multicast_ip, port):
        if multicast_ip not in self.groups:
            self.groups[multicast_ip] = []
        if port not in self.groups[multicast_ip]:
            self.groups[multicast_ip].append(port)
            self.save_groups_to_json()

    def remove_multicast_member(self, multicast_ip, port):
        if multicast_ip in self.groups and port in self.groups[multicast_ip]:
            self.groups[multicast_ip].remove(port)
            self.save_groups_to_json()

    def get_multicast_ports(self, multicast_ip):
        return self.groups.get(multicast_ip, [])
