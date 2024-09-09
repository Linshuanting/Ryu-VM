from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import ipv6
from ryu.lib.packet import icmpv6
from ryu.lib.packet import tcp, udp
from group_manager import GroupManager

class ICMPv6RyuController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ICMPv6RyuController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.group_manager = GroupManager()  # 实例化 GroupManager

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安裝默認流表條目，將所有的 IPv6 包發送到控制器
        match = parser.OFPMatch(eth_type=0x86DD)  # IPv6
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

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
            self.handle_icmpv6(datapath, icmpv6_pkt, ipv6_pkt, in_port, pkt)
            return
        
        udp_pkt = pkt.get_protocol(udp.udp)
        if udp_pkt is not None:
            self.logger.info("Received UDP traffic from %s to %s", ipv6_pkt.src, ipv6_pkt.dst)
            self.handle_udp(datapath, ipv6_pkt, in_port, pkt)


        
    def handle_udp(self, datapath, ipv6_pkt, in_port, pkt):
        
        dst = ipv6_pkt.dst

        if self.is_ipv6_multicast(dst):
            self.logger.info("Received IPv6 multicast traffic from %s to %s", ipv6_pkt.src, ipv6_pkt.dst)
            self.handle_multicast(datapath, ipv6_pkt, in_port, pkt)
            return
        
        self.handle_ipv6(datapath, in_port, pkt, dst)

    def is_ipv6_multicast(self, ip):
        # IPv6 multicast addresses start with 'ff'
        return ip.lower().startswith('ff')

    def handle_multicast(self, datapath, ipv6_pkt, in_port, pkt):
        
        parser = datapath.ofproto_parser
        dst_ip = ipv6_pkt.dst

        # 如果是 mDNS 訊息的話，將其多播出去
        if dst_ip == 'ff02::fb':
            self.send_default_multicast_pkt(datapath, dst_ip, in_port, pkt)
            return

        if self.group_manager.is_ipv6_in_groups(dst_ip) is False:
            self.logger.info("Multicast IPv6 is not in Groups")
            return

        ports = self.group_manager.get_multicast_ports(dst_ip, ipv6=True)
        
        self.send_multicast_pkt(datapath, ports, dst_ip, in_port, pkt)


    def send_multicast_pkt(self, datapath, ports, dst_ip, in_port, pkt):
        
        group_id = self.group_manager.get_or_create_group(datapath, dst_ip, ports)
        
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port,
                                eth_type=ether_types.ETH_TYPE_IPV6, 
                                ipv6_dst=dst_ip)

        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)

    def send_default_multicast_pkt(self, datapath, dst_ip, in_port, pkt):
        # 取得所有端口（除了 in_port）
        ports = [port_no for port_no in datapath.ports.keys() if port_no != in_port]

        # 使用字串串接方式計算 group_id
        group_id = hash(f"{in_port}-{dst_ip}") % (2**32)
        self.group_manager.add_group(datapath, group_id, ports)

        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port,
                            eth_type=ether_types.ETH_TYPE_IPV6, 
                            ipv6_dst=dst_ip)

        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)


    def handle_icmpv6(self, datapath, icmpv6_pkt, ipv6_pkt, in_port, pkt):

        src = ipv6_pkt.src
        dst = ipv6_pkt.dst

        # 忽略 DAD NS Message 
        if src == "::":
            # self.logger.info("Ignoring DAD NS message with unspecified source address.")
            return

        # 根據 ICMPv6 類型進行處理，只有未紀錄在 switch 才需要到控制器詢問該送往哪裡
        if icmpv6_pkt.type_ == icmpv6.ICMPV6_ECHO_REQUEST:
            self.logger.info("Received ICMPv6 Echo Request from %s", src)
            #self.send_icmpv6_reply(datapath, pkt, eth, ipv6_pkt, icmpv6_pkt, in_port)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        elif icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_SOLICIT:
            # 處理鄰居請求的回應邏輯（可以根據你的需求實現回應邏輯）
            self.logger.info("Received Neighbor Solicitation (NS) from %s", src)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        elif icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_ADVERT:
            # 處理鄰居通告的回應邏輯
            self.logger.info("Received Neighbor Advertisement (NA) from %s", src)
            self.handle_ipv6(datapath, in_port, pkt, dst)
        
        # 忽略 SLAAC 自動配置 IPv6 路由器
        # elif icmpv6_pkt.type_ == icmpv6.ND_ROUTER_SOLICIT:
        #     self.logger.info("Received Router Solicitation (RS) from %s", ipv6_pkt.src)
        #     # 處理路由器請求的邏輯
        # elif icmpv6_pkt.type_ == icmpv6.ND_ROUTER_ADVERT:
        #     self.logger.info("Received Router Advertisement (RA) from %s", ipv6_pkt.src)
        #     # 處理路由器通告的邏輯

    def send_icmpv6_reply(self, datapath, pkt, eth, ipv6_pkt, icmpv6_pkt, in_port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 構建以太網頭部
        eth_reply = ethernet.ethernet(
            ethertype=eth.ethertype,
            dst=eth.src,
            src=eth.dst
        )

        # 構建 IPv6 頭部
        ipv6_reply = ipv6.ipv6(
            src=ipv6_pkt.dst,
            dst=ipv6_pkt.src,
            nxt=ipv6_pkt.nxt,
            hop_limit=64
        )

        # 構建 ICMPv6 Echo Reply
        icmpv6_reply = icmpv6.icmpv6(
            type_=icmpv6.ICMPV6_ECHO_REPLY,
            code=icmpv6_pkt.code,
            csum=0,
            data=icmpv6_pkt.data
        )

        # 封裝回覆包
        reply_pkt = packet.Packet()
        reply_pkt.add_protocol(eth_reply)
        reply_pkt.add_protocol(ipv6_reply)
        reply_pkt.add_protocol(icmpv6_reply)
        reply_pkt.serialize()

        actions = [parser.OFPActionOutput(in_port)]
        self.send_packet(datapath, in_port, reply_pkt, actions)
        
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

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != datapath.ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)

    def send_packet(self, datapath, in_port, pkt, actions):
        parser = datapath.ofproto_parser
        data = pkt.data
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=in_port, 
            actions=actions, 
            data=data)
        datapath.send_msg(out)