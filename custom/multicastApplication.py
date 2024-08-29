from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, arp
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
            self.handle_unicast(datapath, in_port, pkt, 'arp')

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            dst = ip_pkt.dst

            # 判斷是否是 multicast 指令，，且我們知道要往哪傳，如果是，則執行 multicast
            if dst in self.group_manager.groups:
                self.logger.info("Dealing with multicast, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_multicast(datapath, self.group_manager.get_multicast_ports(dst), pkt, dst)
            else:
                self.logger.info("Dealing with unicast, src_mac:%s, dst_mac:%s", eth.src, eth.dst)
                self.handle_unicast(datapath, in_port, pkt, dst)

    def handle_multicast(self, datapath, ports, pkt, multicast_ip):
        self.logger.info('Deal with dst_ip:%s', multicast_ip)
        group_id = self.group_manager.get_or_create_group(datapath, multicast_ip, ports)
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=multicast_ip)
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 1, match, actions)

        data = pkt.data
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                  in_port=datapath.ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=data)
        datapath.send_msg(out)

    def handle_unicast(self, datapath, in_port, pkt, dst_ip):
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
            datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

