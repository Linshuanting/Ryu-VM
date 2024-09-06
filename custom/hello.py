from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, arp
from log.log import MyLog
import ipaddress


MULTICAST_GROUPS = {
        "224.1.1.1": [2, 3],  # 靜態配置: 發送到 h2 和 h3
}

class MulticastSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    LOGGER_NAME = 'Multicast_Application'
    LOG_PATH = f'./custom/log/{LOGGER_NAME}.log'
    MULTICAST_IP_PREFIX = '224.0.0.0/4'  # 定义多播 IP 前缀
    # MULTICAST_MAC_PREFIX = '01:00:5e'  # 多播 MAC 地址前缀


    def __init__(self, *args, **kwargs):
        super(MulticastSwitch, self).__init__(*args, **kwargs)
        # 新增一個儲存 Host MAC 的資料結構，類別為 dict(字典)
        self.mac_to_port = {}  # {dpid: {mac: port}}
        self.log = MyLog(self.LOGGER_NAME, self.LOG_PATH)
        self.logger = self.log.get_logger()
        
        # test message
        self.logger.info("This is an info message, starting multicast init")
    
    @set_ev_cls(ofp_event.EventOFPHello, HANDSHAKE_DISPATCHER)
    def _hello_handler(self, ev):
        self.logger.debug('OFPHello received')
        print('OFPHello received')

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_feature_handler(self, ev):

        # processing some informations.
        datapath = ev.msg.datapath
        openFlowProtocol = datapath.ofproto
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # searching suitable match field, without any parameters in paretheses means all parameter should be the same.
        match = parser.OFPMatch()

        # when the flow table match the miss table, the switch will ask controller.
        actions = [parser.OFPActionOutput(openFlowProtocol.OFPP_CONTROLLER,
                                            openFlowProtocol.OFPCML_NO_BUFFER)]

        self.logger.info('---Switch Feature handler start---')
        # add the flow entry to switch, the parameter is : switch_id, priority, match, actions
        self.add_flow(datapath, 0, match, actions)

        group_id = hash("ff38::1") % (2**32)
        buckets = []

        # 为组创建输出端口（例如，将其发送到端口 2 和 3）
        actions1 = [parser.OFPActionOutput(2)]
        buckets.append(parser.OFPBucket(actions=actions1))
        actions2 = [parser.OFPActionOutput(3)]
        buckets.append(parser.OFPBucket(actions=actions2))

        # 创建并发送组表请求
        req = parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,
                                 ofproto.OFPGT_ALL, group_id, buckets)
        datapath.send_msg(req)

        match = parser.OFPMatch(eth_type=0x86DD, ipv6_dst="ff38::1")

        # 使用组 ID 作为动作
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

    
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
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.handle_unicast(datapath, in_port, pkt, 'arp')

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            dst = ip_pkt.dst

            if ip_pkt.dst in MULTICAST_GROUPS:
                # 處理多播
                self.handle_multicast(datapath, MULTICAST_GROUPS[dst], pkt, ip_pkt.dst)
            else:
                # 處理單播或其他
                self.handle_unicast(datapath, in_port, pkt, dst)

    def handle_multicast(self, datapath, ports, pkt, multicast_ip):
        self.logger.info('Deal with dst_ip:%s', multicast_ip)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        data = pkt.data

        group_id = hash(multicast_ip) % (2**32)
        
        # 動態創建Group Table
        self.add_group(datapath, group_id, ports)

        # 安裝流表，將流量導向該Group
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=multicast_ip)
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=data)
        datapath.send_msg(out)
        
    def handle_unicast(self, datapath, in_port, pkt, dst_ip):
        self.logger.info('Deal with in_port:%s, dst_ip:%s', in_port, dst_ip)
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst_mac = eth.dst
        src_mac = eth.src

        # catch switch id.
        datapath_id = datapath.id
        self.mac_to_port.setdefault(datapath_id, {})

        self.logger.info("packet in %s %s %s %s", datapath_id, src_mac, dst_mac, in_port)

        # 將 port 與 switch 和 source mac address 的組合儲存起來。
        self.mac_to_port[datapath_id][src_mac] = in_port

        if dst_mac in self.mac_to_port[datapath.id]:
            out_port = self.mac_to_port[datapath.id][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            self.add_flow(datapath, 1, match, actions)

        self.send_packet(datapath, in_port, pkt, actions)

    def add_group(self, datapath, group_id, ports):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        buckets = []

        for port in ports:
            actions =  [parser.OFPActionOutput(port)]
            buckets.append(parser.OFPBucket(actions=actions))


        # actions = [parser.OFPActionOutput(port) for port in ports]
        # buckets = [parser.OFPBucket(actions=actions)]
        req = parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,
                                 ofproto.OFPGT_ALL, group_id, buckets)
        datapath.send_msg(req)
    
    def send_packet(self, datapath, in_port, pkt, actions
                    ):
        parser = datapath.ofproto_parser
        data = pkt.data
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
