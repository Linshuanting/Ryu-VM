from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3, ofproto_v1_5
import myparser 

class SimpleSwitch(app_manager.RyuApp):
    
    # 選擇支援的openFlow版本，可不只一個版本
    OFP_VERSION = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        
        # super().__init__會去呼叫父類別的initializer__init__
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安裝默認流表條目，將所有的 IPv6 包發送到控制器
        match = parser.OFPMatch(eth_type=0x86DD)  # IPv6
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
    
        print(f"------- test select group adding: {datapath.id} ----------")
        self.send_group_mod(datapath)
    
    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    def send_group_mod(self, datapath):
       
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        ports = [1]
        weight = 100
        watch_port = 0
        watch_group = 0
        buckets = []
        bucket_id = 0

        for port in ports:
            actions = [parser.OFPActionOutput(port)]
            # 為每個端口創建一個桶

            print(f"Actions: {actions}")


            # 只對 group type = select 有效果
            a = parser.OFPGroupBucketPropWeight(type_= ofp.OFPGBPT_WEIGHT, weight=weight)
            # 只對 Group type = Fast failover 有效果
            c = parser.OFPGroupBucketPropWatch(watch=watch_port)
            d = parser.OFPGroupBucketPropWatch(watch=watch_group)

            properties = [a]
            bucket = parser.OFPBucket(
                actions=actions,
                bucket_id = bucket_id, 
                properties=properties)
            buckets.append(bucket)

            bucket_id+=1

            print(f"Buckets: {buckets}")
        

        selection_method='hash' # 指定选择方法为hash
        selection_method_param=0  # 使用默认的哈希参数

        # 使用方法在 myparser.py 裡面，請去確認
        b = myparser.OFPGroupPropExperimenter(
            type_=ofp.OFPGPT_EXPERIMENTER,
            selection_method=selection_method,
            selection_method_param = selection_method_param,
            ipv6_flabel=myparser.OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_FLABEL
            # ipv6_src=myparser.OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_SRC
            )
        
        properties = [b]

        group_id = 1
        command_bucket_id=1
        req = parser.OFPGroupMod(datapath=datapath, 
                                    command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_SELECT, 
                                    group_id=group_id,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets,
                                    properties=properties
                                    )
        # print(f"Sending OFPGroupMod with group_id={group_id}, type={ofp.OFPGT_SELECT}, prop={properties}")
        # print(f"req length: {len(req.serialize())}")
        datapath.send_msg(req)

    