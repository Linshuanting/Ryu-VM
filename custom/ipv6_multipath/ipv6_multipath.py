from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3, ofproto_v1_5
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import ipv6
from ryu.lib.packet import icmpv6
from ryu.lib.packet import tcp, udp
from group_manager_ipv6 import GroupManager
from loop_detection import LoopDetectionTable

class ICMPv6RyuController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ICMPv6RyuController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.group_manager = GroupManager()  # 实例化 GroupManager
        self.loop_detection_tables = {}
        self.count = 1

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安裝默認流表條目，將所有的 IPv6 包發送到控制器
        match = parser.OFPMatch(eth_type=0x86DD)  # IPv6
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

         # 初始化該 switch 的循環檢測表
        dpid = datapath.id
        self.loop_detection_tables[dpid] = LoopDetectionTable(timeout=2)  # 為該 switch 創建獨立的檢測表
    
        print("------- test select group adding ----------")
        self.group_manager.add_group(datapath, self.count, [2])
        self.count+=1
        self.group_manager.add_select_group_with_hash_flabel(datapath, self.count, [2,3])
        self.count+=1

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

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # 確認 packet 來自哪個 switch 的哪個 port
        #self.logger.info("Packet received from switch with DPID: %s on port: %s", datapath.id, in_port)

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # 確認是 IPv6 包
        if eth.ethertype != ether_types.ETH_TYPE_IPV6:
            self.logger.info("Not IPv6 packet")
            return
        # self.logger.info("Handling MAC Address, src_mac:%s, dst_mac:%s", eth.src, eth.dst)

        ipv6_pkt = pkt.get_protocol(ipv6.ipv6)
        if ipv6_pkt is None:
            self.logger.info("IPv6 packet is None")
            return

        # 確認是 ICMPv6 包
        icmpv6_pkt = pkt.get_protocol(icmpv6.icmpv6)
        if icmpv6_pkt is not None:
            # self.logger.info("Handle Icmpv6 packet")
            self.handle_icmpv6(datapath, icmpv6_pkt, ipv6_pkt, in_port, pkt, msg)
            return
        
        udp_pkt = pkt.get_protocol(udp.udp)
        if udp_pkt is not None:
            # self.logger.info("----- In Switch:%s -------", datapath.id)
            # self.logger.info("Received UDP traffic from %s to %s", ipv6_pkt.src, ipv6_pkt.dst)
            self.handle_udp(datapath, ipv6_pkt, in_port, pkt) 

    def handle_udp(self, datapath, ipv6_pkt, in_port, pkt):
        
        dst = ipv6_pkt.dst

        if self.is_ipv6_multicast(dst):
            # self.logger.info("Received IPv6 multicast traffic from %s to %s", ipv6_pkt.src, ipv6_pkt.dst)
            # do nothing
            return
        
        self.logger.info("----- In Switch:%s -------", datapath.id)

        if self.is_ipv6_multipath(datapath.id, dst):
            # 暫定
            self.logger.info("Received IPv6 multipath traffic from %s to %s", ipv6_pkt.src, ipv6_pkt.dst)
            self.handle_multipath(datapath, ipv6_pkt, in_port, pkt)
            return

        self.handle_ipv6(datapath, in_port, pkt, dst)

    def handle_multipath(self, datapath, ipv6_pkt, in_port, pkt):
        
        switch_id = datapath.id
        parser = datapath.ofproto_parser
        dst_ip = ipv6_pkt.dst

        ports = self.group_manager.get_multipath_ports(switch_id, dst_ip, ipv6=True)
        
        group_id = self.group_manager.get_or_create_select_group_with_hash_flabel(datapath, dst_ip, ports, switch_id)

        match = parser.OFPMatch(in_port=in_port,
                                eth_type=ether_types.ETH_TYPE_IPV6, 
                                ipv6_dst=dst_ip)
        
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)

    def handle_icmpv6(self, datapath, icmpv6_pkt, ipv6_pkt, in_port, pkt, msg):

        src = ipv6_pkt.src
        dst = ipv6_pkt.dst

        # 忽略 DAD NS Message 
        if src == "::":
            # self.logger.info("Ignoring DAD NS message with unspecified source address.")
            return

        if self.detect_duplicated(datapath.id, msg):
            return 

        # 根據 ICMPv6 類型進行處理，只有未紀錄在 switch 才需要到控制器詢問該送往哪裡
        if icmpv6_pkt.type_ == icmpv6.ICMPV6_ECHO_REQUEST:
            self.logger.info("----- In Switch:%s -------", datapath.id)
            self.logger.info("Received ICMPv6 Echo Request from %s", src)
            #self.send_icmpv6_reply(datapath, pkt, eth, ipv6_pkt, icmpv6_pkt, in_port)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        elif icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_SOLICIT:
            # 處理鄰居請求的回應邏輯（可以根據你的需求實現回應邏輯）
            self.logger.info("----- In Switch:%s -------", datapath.id)
            self.logger.info("Received Neighbor Solicitation (NS) from %s", src)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        elif icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_ADVERT:
            # 處理鄰居通告的回應邏輯
            self.logger.info("----- In Switch:%s -------", datapath.id)
            self.logger.info("Received Neighbor Advertisement (NA) from %s", src)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        
        # 忽略 SLAAC 自動配置 IPv6 路由器
        # elif icmpv6_pkt.type_ == icmpv6.ND_ROUTER_SOLICIT:
        #     self.logger.info("Received Router Solicitation (RS) from %s", ipv6_pkt.src)
        #     # 處理路由器請求的邏輯
        # elif icmpv6_pkt.type_ == icmpv6.ND_ROUTER_ADVERT:
        #     self.logger.info("Received Router Advertisement (RA) from %s", ipv6_pkt.src)
        #     # 處理路由器通告的邏輯
        
    def handle_ipv6(self, datapath, in_port, pkt, dst_ip):
        
        self.logger.info('Deal with in_port:%s, dst_ip:%s', in_port, dst_ip)
        
        parser = datapath.ofproto_parser
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst_mac = eth.dst
        src_mac = eth.src
        datapath_id = datapath.id
        self.mac_to_port.setdefault(datapath_id, {})
        self.mac_to_port[datapath_id][src_mac] = in_port

        if dst_mac in self.mac_to_port[datapath.id]:
            out_port = self.mac_to_port[datapath.id][dst_mac]
        else:
            out_port = datapath.ofproto.OFPP_FLOOD

        self.logger.info('Out port:%s, dst_ip:%s', out_port, dst_ip)

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != datapath.ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)

    def detect_duplicated(self, dpid, msg):
        # 檢查該 switch 的循環檢測表是否存在
        if dpid not in self.loop_detection_tables:
            self.loop_detection_tables[dpid] = LoopDetectionTable(timeout=2)

        # 檢查封包是否是循環的
        loop_detection_table = self.loop_detection_tables[dpid]
        if loop_detection_table.is_packet_duplicate(msg.data):
            self.logger.info(f"Dropping duplicate packet on switch {dpid} to prevent loop")
            return True # 丟棄封包

        # 添加封包到該 switch 的循環檢測表
        loop_detection_table.add_packet(msg.data)

        return False
    
    def select_output_port(self, flow_label, ports):
            # Use flow label modulus to decide output port
            return ports[flow_label % len(ports)] 
    
    # 暫定
    def is_ipv6_multipath(self, switch_id, dst_ip):
        return self.group_manager.is_ipv6_in_groups(switch_id, dst_ip)

    def is_ipv6_multicast(self, ip):
        # IPv6 multicast addresses start with 'ff'
        return ip.lower().startswith('ff')

    def send_packet(self, datapath, in_port, pkt, actions):
        parser = datapath.ofproto_parser
        data = pkt.data
        match = parser.OFPMatch(in_port=in_port)
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            match=match, 
            actions=actions, 
            data=data)
        datapath.send_msg(out)