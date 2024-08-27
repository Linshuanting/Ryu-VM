from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, arp
from log.log import MyLog
import ipaddress

class MulticastSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    LOGGER_NAME = 'Multicast_Application'
    LOG_PATH = f'./custom/log/{LOGGER_NAME}.log'
    MULTICAST_IP_PREFIX = '224.0.0.0/4'  # 定义多播 IP 前缀
    MULTICAST_MAC_PREFIX = '01:00:5e'  # 多播 MAC 地址前缀


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
        parser = datapath.ofproto_parser

        # searching suitable match field, without any parameters in paretheses means all parameter should be the same.
        match = parser.OFPMatch()

        # when the flow table match the miss table, the switch will ask controller.
        actions = [parser.OFPActionOutput(openFlowProtocol.OFPP_CONTROLLER,
                                            openFlowProtocol.OFPCML_NO_BUFFER)]

        # add the flow entry to switch, the parameter is : switch_id, priority, match, actions
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
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        src = eth.src
        dst = eth.dst
        self.logger.info('From ' + src + ' to ' + dst)

        # 更新 MAC 地址到端口映射
        self.mac_to_port.setdefault(datapath.id, {})
        self.mac_to_port[datapath.id][src] = in_port

        self.logger.info("packet in %s %s %s %s", datapath.id, src, dst, in_port)

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.handle_arp(datapath, in_port, pkt)
        
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if self.is_multicast_ip(ip_pkt.dst):
                self.handle_multicast(datapath, in_port, pkt)
            else:
                self.handle_unicast(datapath, in_port, pkt, ip_pkt.dst)
        

    def is_multicast_ip(self, ip):
        # 判断 IP 是否在 224.0.0.0/4 范围内
        ip_octets = [int(octet) for octet in ip.split('.')]
        return ip_octets[0] >= 224 and ip_octets[0] <= 239

    def handle_arp(self, datapath, port, pkt):
        arp_pkt = pkt.get_protocol(arp.arp)
    
        # 处理 ARP 请求
        if arp_pkt.opcode == arp.ARP_REQUEST:

            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
            self.send_packet(datapath, port, pkt, actions)

        # 处理 ARP 响应
        elif arp_pkt.opcode == arp.ARP_REPLY:
            if self.is_multicast_ip(arp_pkt.src_ip):
                # 存储 ARP 响应中的 MAC 和端口信息
                self.mac_to_port.setdefault(datapath.id, {})[arp_pkt.src_mac] = port

                # 根据新的 MAC 地址写入流表
                for mac_addr, out_port in self.mac_to_port[datapath.id].items():
                    match = datapath.ofproto_parser.OFPMatch(eth_dst=mac_addr)
                    actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                    self.add_flow(datapath, 1, match, actions)
            else:
                # 处理单播 IP 地址的 ARP 响应
                self.mac_to_port.setdefault(datapath.id, {})[arp_pkt.src_ip] = port
                # 更新流表
                match = datapath.ofproto_parser.OFPMatch(eth_dst=arp_pkt.src_mac)
                actions = [datapath.ofproto_parser.OFPActionOutput(port)]
                self.add_flow(datapath, 1, match, actions)


    def handle_unicast(self, datapath, in_port, pkt, dst_ip):
        # 检查目的 MAC 是否在 mac_to_port 中
        dst_mac = None
        for mac_addr in self.mac_to_port[datapath.id]:
            if self.mac_to_port[datapath.id][mac_addr] == in_port:
                dst_mac = mac_addr
                break

        if dst_mac:
            out_port = self.mac_to_port[datapath.id].get(dst_mac)
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        else:
            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
        
        self.send_packet(datapath, in_port, pkt, actions)


    def handle_multicast(self, datapath, in_port, pkt):
        # 发送到所有存储的端口
        actions = [datapath.ofproto_parser.OFPActionOutput(port) for port in self.mac_to_port[datapath.id].values()]
        self.send_packet(datapath, in_port, pkt, actions)

    def send_packet(self, datapath, port, pkt, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt.serialize()
        data = pkt.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=port, actions=actions, data=data)
        datapath.send_msg(out)
    

