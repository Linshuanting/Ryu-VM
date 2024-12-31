from topo_learn import SimpleSwitch15
from typing import List, Dict, Tuple, Set
import selection_method_parser as sm_parser

class MyController(SimpleSwitch15):

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)
        print("My Controller Initialize")
        self.group_id_counter = 1

    def test(self):
        # test function
        pass

    def send_instruction(self) -> Dict[str, list]:

        print ("------ start send instruction to switchs ------")

        flow = self.topo.get_commodities_and_paths()
        for commodity, context in flow.items():
            print(f"-- {commodity} --")
            switch_to_port_bandwidth = {}
            
            for u, v_bw_list in context.items():
                if self.topo.is_host(u):
                    continue
                port_bw_list = []
                for v, bw in v_bw_list:
                    port_u, port_v = self.topo.get_link(u, v)
                    port_bw_list.append((port_u, bw))
                switch_to_port_bandwidth[u] = port_bw_list

            for dp_id, port_bw_list in switch_to_port_bandwidth.items():
                dp = self.topo.get_datapath(dp_id)
                self.send_group_selection_method(dp, port_bw_list)

    def send_group_selection_method(self, datapath, port_weight_list):

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
                                    group_id=self.group_id_counter,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets,
                                    properties=properties
                                    )
        
        datapath.send_msg(req)
        self.group_id_counter+=1
