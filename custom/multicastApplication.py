from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, ipv6, packet, arp, udp
from log.log import MyLog
from group_manager import GroupManager


MULTICAST_GROUPS = {
        "224.1.1.1": [2, 3],  # 靜態配置: 發送到 h2 和 h3
}

class MulticastSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    LOGGER_NAME = 'Multicast_Application'
    LOG_PATH = f'./custom/log/{LOGGER_NAME}.log'
    MULTICAST_IP_PREFIX = '224.0.0.0/4'  # 定义多播 IP 前缀
    MULTICAST_IP_PREFIX_V6 = 'ff00::/8'  # 定義 IPv6 多播 IP 前綴

    def __init__(self, *args, **kwargs):
        super(MulticastSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}  # {dpid: {mac: port}}
        self.log = MyLog(self.LOGGER_NAME, self.LOG_PATH)
        self.logger = self.log.get_logger()
        self.group_manager = GroupManager()  # 实例化 GroupManager
        self.logger.info("This is an info message, starting multicast init")

    @set_ev_cls(ofp_event.EventOFPHello, HANDSHAKE_DISPATCHER)
    def _hello_handler(self, ev):
        self.logger.debug('OFPHello received')
        print('OFPHello received')

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_feature_handler(self, ev):
        self.logger.info('---Switch Feature handler start---')
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(datapath.ofproto.OFPP_CONTROLLER,
                                          datapath.ofproto.OFPCML_NO_BUFFER)]
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
        # 獲取 packet 資料
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # 若是 arp 指令，則執行最基本的路由
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.handle_unicast(datapath, in_port, pkt, 0,'ARP')

        udp_pkt = pkt.get_protocol(udp.udp)
        if udp_pkt is not None:
            self.logger.info("Received iperf UDP traffic")

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            dst = ip_pkt.dst
            src = ip_pkt.src

            # 判斷是否是 multicast 指令，，且我們知道要往哪傳，如果是，則執行 multicast
            if dst in self.group_manager.get_ipv4_groups():
                self.logger.info("Dealing with multicast_ipv4, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_multicast(datapath, self.group_manager.get_multicast_ports(dst), pkt, dst, ip_version=4)
            else:
                self.logger.info("Dealing with unicast_ipv4, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_unicast(datapath, in_port, pkt, dst)

        elif eth.ethertype == ether_types.ETH_TYPE_IPV6:
            ip6_pkt = pkt.get_protocol(ipv6.ipv6)
            dst = ip6_pkt.dst
            src = ip6_pkt.src
        
            # Ignore NDP or multicast addresses
            if dst.startswith("ff02::"):
                # self.logger.info("Ignoring NDP IPv6 address: %s", dst)
                self.handle_unicast(datapath, in_port, pkt, dst, 'NDP')
                return
            
            # 判斷是否是 multicast 指令，，且我們知道要往哪傳，如果是，則執行 multicast
            if dst in self.group_manager.get_ipv6_groups():
                self.logger.info("Dealing with multicast_ipv6, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_multicast(datapath, self.group_manager.get_multicast_ports(dst, ipv6=True), pkt, src, dst, ip_version=6)
            else:
                self.logger.info("Dealing with unicast_ipv6, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_unicast(datapath, in_port, pkt, dst)


    def handle_multicast(self, datapath, ports, pkt, src, multicast_ip, ip_version):
        self.logger.info('Deal with src_ip:%s, dst_ip:%s, protocols:ipv%s', src, multicast_ip, ip_version)
        group_id = self.group_manager.get_or_create_group(datapath, multicast_ip, ports)
        parser = datapath.ofproto_parser
        
        # 根据 IP 版本设置匹配规则
        if ip_version == 4:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=multicast_ip)
        elif ip_version == 6:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IPV6, ipv6_dst=multicast_ip)
        
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        data = pkt.data
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                  in_port=datapath.ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=data)
        datapath.send_msg(out)

    def handle_unicast(self, datapath, in_port, pkt, dst_ip, pkt_type="IP"):
        
        if pkt_type == 'NDP':
            pass
        elif pkt_type == 'ARP':
            self.logger.info('Deal with in_port:%s, dst_ip:%s, protocols:%s', in_port, dst_ip, pkt_type)
        else:
            self.logger.info('Deal with in_port:%s, dst_ip:%s, protocols:%s', in_port, dst_ip, pkt_type)
        
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
            datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=datapath.ofproto.OFPP_CONTROLLER, actions=actions, data=data)
        datapath.send_msg(out)

