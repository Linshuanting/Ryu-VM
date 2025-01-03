from topo_learn import SimpleSwitch15
from typing import List, Dict, Tuple, Set
import selection_method_parser as sm_parser
from ryu.lib.packet import ethernet, ether_types
from multi_db import MultiGroupDB
from utils import print_dict

class MyController(SimpleSwitch15):

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)
        print("My Controller Initialize")
        self.group_id_counter = 1
        self.priority = 100
        self.multi_db = MultiGroupDB()

    def test(self):
        # test function
        dp_id, group_id = 1, 9999
        dp = self.topo.get_datapath(dp_id)
        self.send_flowMod_to_switch(dp, 1, "ff38::1", group_id)
        pass

    def send_instruction(self) -> Dict[str, list]:

        print ("------ start send instruction to switchs ------")

        commodities = self.topo.get_commodities()
        for commodity in commodities:
            paths = self.topo.get_paths(commodity)
            print(f"-- {commodity} --")
            for tree in paths:
                switch_to_port_bandwidth = {}
                switch_to_inport = {}
                nodes = set()
                print(f"---- tree ----")
                
                for (u, v), bw in tree.items():
                    port_u, port_v = self.topo.get_link(u, v)
                    
                    # 判斷每個 switch 要流出的 port，以及其權重
                    if u not in switch_to_port_bandwidth:
                        switch_to_port_bandwidth[u] = [(port_u, bw)]
                    else:
                        switch_to_port_bandwidth[u].append((port_u, bw))
                    # 判斷每個 switch 流入口，來當作 match 條件
                    if v not in switch_to_inport:
                        switch_to_inport[v] = [port_v]
                    else:
                        switch_to_inport[v].append(port_v)

                    if not u.startswith('h'):
                        nodes.add(u)
                    if not v.startswith('h'):
                        nodes.add(v)

                multi_ip = self.multi_db.assign_internal_ip(commodity)
                if multi_ip is None:
                    # 測試用 ip
                    multi_ip = "ff38::8888"
                print(f"Multi IP:{multi_ip}")
                print_dict(tree)
                for dp_id in nodes:
                    dp = self.topo.get_datapath(dp_id)
                    group_id = self.group_id_counter
                    port_bw_list = switch_to_port_bandwidth[dp_id]
                    # 處理每個 switch 的 output 流向
                    self.send_group_selection_method(dp, port_bw_list, group_id)
                    # 處理每個 switch 的 inport 判斷
                    for inport in switch_to_inport[dp_id]:
                        self.send_flowMod_to_switch(dp, inport, multi_ip, group_id)
                    
                    self.group_id_counter+=1

    def send_flowMod_to_switch(self, datapath, inport, multi_ip, group_id):
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(
            in_port=inport,
            eth_type=ether_types.ETH_TYPE_IPV6,
            ipv6_dst=multi_ip
        )
        actions = [parser.OFPActionGroup(group_id)]
        # actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, self.priority, match, actions)

    def send_group_selection_method(self, datapath, port_weight_list, group_id):

        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        buckets = []
        bucket_id = 0

        selection_method = "hash"
        selection_method_param = 0

        for port, weight in port_weight_list:
            actions = [parser.OFPActionOutput(port)]
            properties = [parser.OFPGroupBucketPropWeight(type_= ofp.OFPGBPT_WEIGHT, weight=weight)]
            bucket = parser.OFPBucket(
                actions=actions,
                bucket_id=bucket_id,
                properties = properties
            )
            buckets.append(bucket)
            bucket_id+=1
        
        property = sm_parser.OFPGroupPropExperimenter(
            type_=ofp.OFPGPT_EXPERIMENTER,
            selection_method=selection_method,
            selection_method_param = selection_method_param,
            ipv6_flabel=sm_parser.OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_FLABEL
        )
        properties = [property]
        req = parser.OFPGroupMod(datapath=datapath, 
                                    command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_SELECT, 
                                    group_id=group_id,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets,
                                    properties=properties
                                    )
        
        datapath.send_msg(req)

    def assign_commodities_hosts_to_multi_ip(self, commodities_data):
        for data in commodities_data:
            commodity = data['name']
            self.multi_db.create_group_for_commodity(commodity)
            self.multi_db.add_host_to_group(commodity, data['source'])
            for dst in data['destinations']:
                self.multi_db.add_host_to_group(commodity, dst)