from topo_learn import SimpleSwitch15
from typing import List, Dict, Tuple, Set
import selection_method_parser as sm_parser
from ryu.lib.packet import ethernet, ether_types
from multi_db import MultiGroupDB
from multi_flabel import MultiFLabelDB
from mininet_connect import MininetSSHManager
from utils import print_dict, append_to_json, initialize_file

class MyController(SimpleSwitch15):

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)
        print("My Controller Initialize")
        self.group_id_counter = 1
        self.priority = 100
        self.multi_db = MultiGroupDB()
        self.multi_flabel_db = MultiFLabelDB()
        self.mininet = MininetSSHManager()
        self.file_name = "~/mininet/custom/output.json"
        initialize_file(self.file_name)

    def test(self):
        # test function
        dp_id, group_id = 1, 9999
        dp = self.topo.get_datapath(dp_id)
        self.send_flowMod_to_switch(dp, 1, "ff38::1", group_id)
        pass

    def run(self, commodities):

        self.assign_commodities_hosts_to_multi_ip(commodities)
        self.assign_commodities_hosts_to_multi_Flabel_Group(commodities)
        self.send_instruction()
        # self.connect_to_host_and_send_setting_cmd(commodities)
        
        # 以後用來新增 ssh 連線用的
        # 目前還未完工，會顯示連線失敗，需要做修正
        # self.mininet.set_hosts(self.topo.get_all_host_single_ipv6())
        # print(self.mininet.batch_run_command("ip -6 route show"))

    def send_instruction(self):

        print ("------ start send instruction to switchs ------")

        commodities = self.topo.get_commodities() # commodities name List
        for commodity in commodities:
            paths = self.topo.get_paths(commodity)
            print(f"-- {commodity} --")
            for tree in paths:
                switch_to_port_bandwidth = {}
                switch_to_inport = {}
                nodes = set()
                tree_bandwidth = 0
                print(f"---- tree ----")
                
                for (u, v), bw in tree.items():
                    port_u, port_v = self.topo.get_link(u, v)
                    
                    # 判斷每個 switch 要流出的 port，以及其權重
                    if u not in switch_to_port_bandwidth:
                        switch_to_port_bandwidth[u] = [(port_u, bw)]
                        tree_bandwidth = bw
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
                    

                # multi_ip = self.multi_db.assign_internal_ip(commodity)
                # if multi_ip is None:
                #     # 測試用 ip
                #     multi_ip = "ff38::8888"
                # print(f"Multi IP:{multi_ip}")

                multi_ip = self.multi_db.get_commodity_ip(commodity)
                src, dsts = self.multi_db.get_src_host_from_commodity(commodity), self.multi_db.get_dst_hosts_from_commodity(commodity)
                print(f"Multi IP:{multi_ip}")
                print(f"src:{src}, dsts:{dsts}")
                multi_flabel_val, multi_flabel_mask = self.multi_flabel_db.assign_subgroup(commodity)
                print(f"Multi Flow Label:{multi_flabel_val:05x}, Flow Label Mask:{multi_flabel_mask:05x}")
                print(f"Multi Flow Bandwidth:{tree_bandwidth}")
                self.record_data_to_json(commodity, multi_ip, src, dsts, multi_flabel_val, multi_flabel_mask, tree_bandwidth)

                print_dict(tree)
                for dp_id in nodes:
                    dp = self.topo.get_datapath(dp_id)
                    group_id = self.group_id_counter
                    port_bw_list = switch_to_port_bandwidth[dp_id]
                    # 處理每個 switch 的 output 流向
                    if len(port_bw_list) > 1:
                        self.send_group_multicast_method(dp, port_bw_list, group_id)
                    else:
                        self.send_group_selection_method(dp, port_bw_list, group_id)
                    # 處理每個 switch 的 inport 判斷
                    for inport in switch_to_inport[dp_id]:
                        # self.send_flowMod_to_switch(dp, inport, group_id, multi_ip)
                        self.send_flowMod_to_switch(dp, inport, group_id, multi_ip=multi_ip, multi_flabel_val=multi_flabel_val, multi_flabel_mask=multi_flabel_mask)
                    
                    self.group_id_counter+=1
    
    def connect_to_host_and_send_setting_cmd(self, commodities):
        
        self.mininet.set_hosts(self.topo.get_all_host_single_ipv6())
        print(self.topo.get_all_host_single_ipv6())
        self.mininet.print_hosts()
        
        for commodity in commodities:
            print(f"執行 {commodity} 中，連接 host 的指令")
            group_ip = self.multi_db.get_commodity_ip(commodity['name'])
            src_host = commodity['source']
            dst_hosts = commodity['destinations']
            self.mininet.run_source_cmd(src_host, group_ip)
            self.mininet.run_destinations_cmd(dst_hosts, group_ip)

    def send_flowMod_to_switch(self, 
                               datapath, 
                               inport, 
                               group_id, 
                               multi_ip=None, 
                               multi_flabel_val = None,
                               multi_flabel_mask = None):
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(
            in_port=inport,
            eth_type=ether_types.ETH_TYPE_IPV6,
            ipv6_dst=multi_ip,
            ipv6_flabel = (multi_flabel_val, multi_flabel_mask) # mask 後面 12 bits(3 bytes)，只看前 8 bits
        )
        actions = [parser.OFPActionGroup(group_id)]
        # actions = [parser.OFPActionOutput(1)]
        self.add_flow(datapath, self.priority, match, actions)
    
    def send_group_multicast_method(self, datapath, port_weight_list, group_id):

        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        buckets = []
        bucket_id = 0

        for port, weight in port_weight_list:
            actions = [parser.OFPActionOutput(port)]
            bucket = parser.OFPBucket(
                actions=actions,
                bucket_id=bucket_id,
            )
            buckets.append(bucket)
            bucket_id+=1
        
        req = parser.OFPGroupMod(datapath=datapath, 
                                    command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_ALL, 
                                    group_id=group_id,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets
                                    )
        
        datapath.send_msg(req)

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
            self.multi_db.add_host_to_group(commodity, src_host=data['source'], dst_hosts=data['destinations'])
    
    def assign_commodities_hosts_to_multi_Flabel_Group(self, commodities_data):
        for data in commodities_data:
            commodity = data['name']
            self.multi_flabel_db.create_group_for_commodity(commodity)
            self.multi_flabel_db.add_host_to_group(commodity, data['source'])
            for dst in data['destinations']:
                self.multi_flabel_db.add_host_to_group(commodity, dst)
            
    def record_data_to_json(self, commodity, multi_ip, src, dsts, multi_flabel_val, multi_flabel_mask, tree_bandwidth):
        """
        組織資料並記錄到 JSON 檔案。
        """
        # 組織要儲存的資料
        data = {
            "commodity": commodity,
            "multi_ip": multi_ip,
            "src": src,
            "dsts": dsts,
            "multi_flabel_val": f"{multi_flabel_val:05x}",
            "multi_flabel_mask": f"{multi_flabel_mask:05x}",
            "tree_bandwidth": tree_bandwidth
        }
        
        # 呼叫函式儲存資料
        append_to_json(self.file_name, data)