from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link, get_host, get_all_link
import networkx as nx
from ryu.lib import hub

class ShortestPathController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ShortestPathController, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.network = nx.DiGraph()  # 建立拓撲圖
        self.mac_to_dpid = {}  # MAC 位址對應的 switch
        self.mac_to_port = {}  # MAC 位址對應的 port
        self.datapaths = {}  # switch 物件
        self.hosts = {}  # ⭐ 記錄 MAC 所在的 switch

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """ 安裝預設規則，將未知封包發送到控制器 """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.datapaths[datapath.id] = datapath  # 存儲 switch 資訊

    def add_flow(self, datapath, priority, match, actions):
        """ 添加流表規則 """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        """ 監聽 switch 加入事件，更新網路拓撲 """
        self.update_topology()

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        """ 監聽 link 加入事件，更新網路拓撲 """
        self.update_topology()

    def update_topology(self):
        """ 更新 NetworkX 拓撲，並強制學習所有 switch、link 和 host """
        self.network.clear()

        # 取得所有 switch
        switches = get_switch(self.topology_api_app, None)
        for switch in switches:
            self.network.add_node(switch.dp.id)

        # 取得所有 link
        links = get_all_link(self)
        for link in links:
            self.network.add_edge(link.src.dpid, link.dst.dpid, port=link.src.port_no)
            self.network.add_edge(link.dst.dpid, link.src.dpid, port=link.dst.port_no)

        self.logger.info(f"拓撲更新: Switches: {[s.dp.id for s in switches]}")
        self.logger.info(f"拓撲更新: Links: {[(l.src.dpid, l.dst.dpid) for l in links]}")

        # 強制加入主機
        hosts = get_host(self, None)
        for host in hosts:
            mac = host.mac
            dpid = host.port.dpid
            port = host.port.port_no
            self.hosts[mac] = dpid

            self.network.add_node(mac)
            self.network.add_edge(mac, dpid, port=port)
            self.network.add_edge(dpid, mac, port=port)

            self.logger.info(f"拓撲更新: 加入主機 {mac} <-> Switch {dpid}, Port {port}")

        self.logger.info(f"完整拓撲圖: {self.network.edges(data=True)}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """ 當 switch 送出 Packet-In 時處理 """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # 忽略 LLDP
        if eth.ethertype == 0x88cc:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_dpid[src] = dpid
        self.mac_to_port[src] = in_port

        # ⭐ 如果 MAC 位址是新的，將其加入拓撲
        if src not in self.hosts:
            self.hosts[src] = dpid
            self.network.add_node(src)
            self.network.add_edge(src, dpid, port=in_port)
            self.network.add_edge(dpid, src, port=in_port)
            self.logger.info(f"加入主機 {src} <-> Switch {dpid}, Port {in_port}")
            self.logger.info(f"完整拓撲圖: {self.network.edges(data=True)}")

        # 檢查目標 MAC 地址是否已知
        if dst in self.hosts:
            dst_dpid = self.hosts[dst]
            path = self.get_shortest_path(src, dst)

            if path and len(path) > 1:
                self.logger.info(f"最短路徑 {src} -> {dst}: {path}")
                self.install_path(path, src, dst)
                out_port = self.network[dpid][path[1]]['port']
            else:
                self.logger.warning(f"找不到 {src} -> {dst} 的路徑，改用 Flood")
                out_port = ofproto.OFPP_FLOOD
        else:
            out_port = ofproto.OFPP_FLOOD  # 若未知 MAC，則 Flood

        actions = [parser.OFPActionOutput(out_port)]
    
        # 轉發封包
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=msg.data)
        datapath.send_msg(out)

    def get_shortest_path(self, src, dst):
        """ 使用 Dijkstra 演算法尋找最短路徑 (可計算 Host) """
        try:
            if src not in self.network or dst not in self.network:
                self.logger.warning(f"{src} 或 {dst} 不在拓撲中！")
                return None

            self.logger.info(f"Dijkstra 計算 {src} -> {dst}")
            path = nx.shortest_path(self.network, source=src, target=dst)
            if len(path) < 2:
                return None
            return path
        except nx.NetworkXNoPath:
            self.logger.warning(f"Dijkstra 找不到 {src} -> {dst} 的路徑")
            return None
