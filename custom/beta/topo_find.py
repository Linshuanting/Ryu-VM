from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_5
from ryu.ofproto import inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import lldp
from ryu.lib.packet import ipv6, icmpv6, tcp
from ryu.lib import hub
from ryu.exception import RyuException
from data_structure.topo_data_structure import Topology
from ryu.app.wsgi import WSGIApplication
import threading
import os, re


from algorithm.Dijkstra import NetworkGraph
from data_structure.packet import Icmpv6Packet, NDPPacket, LLDPPacket

class TopoFind(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopoFind, self).__init__(*args, **kwargs)
        self.topo = Topology()
        self.networkGraph=NetworkGraph()
        self.topo_monitor_thread = hub.spawn(self._topo_monitor)
        # self.monitor_thread = hub.spawn(self._monitor)

    def initialize(self):

        self.logger.info("Mininet 停止，Ryu 重新初始化...")
        self.topo.reset()
        self.networkGraph.initialize_graph()

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        """ 追蹤交換機的連線與斷開 """
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:  # 交換機連線
            self.topo.set_datapath(datapath=datapath)
            self.logger.info(f"交換機 {datapath.id} 已連接")
        elif ev.state == DEAD_DISPATCHER:  # 交換機斷開
            if self.topo.get_datapath(datapath.id):
                self.topo.del_datapath(datapath=datapath)
                self.networkGraph.del_node(datapath.id)
                self.logger.info(f"交換機 {datapath.id} 已斷開")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        
        msg = ev.msg
        datapath = ev.msg.datapath

        self.logger.info(f'** Connect to switch {datapath.id}')

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        portRequestmsg = parser.OFPPortDescStatsRequest(datapath)
        datapath.send_msg(portRequestmsg)
    
    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def _port_status_handler(self,ev):
        
        msg=ev.msg
        dp=msg.datapath
        body=ev.msg.body
        
        for p in body:
            self.logger.info(f'** switch {dp.id} get the PortDesc in Port:{p.port_no}')
            self.logger.info("Port Attributes: %s", p.__dict__)


            if p.port_no != ofproto_v1_5.OFPP_CONTROLLER and p.port_no != ofproto_v1_5.OFPP_LOCAL:
                # self.topo.set_port_in_switch(dp.id, p.port_no)
                self.topo.set_sw_mac_to_context(p.hw_addr, dp.id, p.port_no)
                self.topo.set_datapath(dp, dp.id)
                self.send_lldp_out(dp, p.port_no)
                self.del_link_to_database(p.hw_addr)
                self.topo.del_host(p.hw_addr)
            else:
                self.logger.info(f'*** skip the PortDesc in Port:{p.port_no}')
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            self._lldp_packet_in_handler(ev)
            return
        
        # 取得 IPv6 封包
        ipv6_pkt = pkt.get_protocol(ipv6.ipv6)
        if ipv6_pkt is None:
            return  # 如果不是 IPv6，直接忽略
        
        icmpv6_pkt = pkt.get_protocol(icmpv6.icmpv6)
        if icmpv6_pkt is not None:
            self._icmpv6_packet_in_handler(ev)
            # 如果是 NDP 封包（135, 136, 133, 134, 137），則忽略
            if icmpv6_pkt.type_ in [135, 136, 133, 134, 137]:
                return  # 忽略 NDP 封包
            if icmpv6_pkt.type_ is icmpv6.MLDV2_LISTENER_REPORT:
                return  # 忽略 MLD 封包 
        
        src_ipv6 = ipv6_pkt.src
        dst_ipv6 = ipv6_pkt.dst
        
        if dst_ipv6 == "ff02::fb":
            # self.logger.info(f"收到 mDNS 封包: SRC={src_ipv6}, DST={dst_ipv6}")
            return
        
        if dst_ipv6.startswith("ff"):
            self.logger.info(f"收到多播封包: SRC={src_ipv6}, DST={dst_ipv6}")
            # TODO
            return

        print(f"取得 IPv6 封包: SRC={src_ipv6}, DST={dst_ipv6}")
        
        src_name = self.topo.get_hostName_from_ip(src_ipv6)[0]
        dst_name = self.topo.get_hostName_from_ip(dst_ipv6)[0]

        if src_name is None or dst_name is None:
            self.logger.info(f"無效的 src: {src_name}, dst: {dst_name}")
            return
        
        self.logger.info(f'src name: {src_name}, dst name: {dst_name}')
        
        path = self.write_path_to_switch(src_name, dst_name)
        
        next_node = self.networkGraph.get_next_hop(path)[datapath.id]
        port_u, port_v = self.topo.get_link(datapath.id, next_node)

        self.send_pkt_msg(datapath=datapath, port=port_u, data=msg.data)

    def _lldp_packet_in_handler(self, ev):
        
        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg)
        except LLDPPacket.LLDPUnknownFormat as e:
            return
        
        dst_dpid = msg.datapath.id
        dst_port_no = msg.match['in_port']

        self.logger.info(f'***** Get the lldp packet in switch {dst_dpid}, port:{dst_port_no} from switch {src_dpid}, port:{src_port_no} ')
        self.add_link_to_database(src_dpid, dst_dpid, src_port_no, dst_port_no)
    
    def send_lldp_out(self, datapath, port):
        
        self.logger.info(f'**** send the lldp packet in switch {datapath.id}, port:{port}')
        data = LLDPPacket.lldp_packet(datapath.id, port)
        self.send_pkt_msg(datapath, port, data)

    def _icmpv6_packet_in_handler(self, ev):
        msg = ev.msg
        dp=msg.datapath
        in_port=msg.match['in_port']

        try:
            data = Icmpv6Packet.icmpv6_parse(msg)
        except Icmpv6Packet.Icmpv6UnknownFormat as e:
            # self.logger.warning(f"Unknown NDP packet format: {e}")
            return
        
        # 判斷這個封包是否是 DAD 封包，是才繼續做
        if data['src_ip'] == "::" and data['icmpv6_type'] == icmpv6.ND_NEIGHBOR_SOLICIT:
            self.handle_ndp_dad(dp, in_port, data)
            return
        # NS
        if data['icmpv6_type'] == icmpv6.ND_NEIGHBOR_SOLICIT:
            self.handle_ndp_ns(dp, in_port, data)
            return
        # RS
        if data['icmpv6_type'] == icmpv6.ND_ROUTER_SOLICIT:
            self.handle_ndp_rs(dp, in_port, data)
            return
        # MLD
        if data['icmpv6_type'] == icmpv6.MLDV2_LISTENER_REPORT:
            self.handle_mld_report(dp, in_port, data)
            return
    
    def handle_ndp_dad(self, dp, in_port, data):
        
        if (self.topo.contain_sw_mac(data['src_mac'])):
            return

        if (self.topo.contain_IP(data['target_ip']) 
            and data['target_ip'].startswith('ff') is False):
            # reply dad msg
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is NDP DAD packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        print(f'                         , the tar_ip:{data["target_ip"]} ')

        self.topo.set_host(data['src_mac'], data['target_ip'], dp.id, in_port)
        self.add_link_to_database(data['src_mac'], dp.id, 0, in_port)
        self.add_link_to_database(dp.id, data['src_mac'], in_port, 0)

    def handle_ndp_ns(self, dp, in_port, data):

        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is NDP NS packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.add_link_to_database(data['src_mac'], dp.id, 0, in_port)
        self.add_link_to_database(dp.id, data['src_mac'], in_port, 0)
        self.send_ndp_na_out(dp, in_port, data)

    def send_ndp_na_out(self, datapath, port, data):
        
        src_mac = self.topo.get_host_mac(host_ip=data['target_ip'])
        if src_mac is None:
            print(f"target mac {data['target_ip']} is not find")
            return

        # 發送 NDP (NA) 封包
        pkt = NDPPacket.ndp_packet(icmpv6.ND_NEIGHBOR_ADVERT, 
                                   src_mac,
                                   data['src_mac'],
                                   data['target_ip'], 
                                   data['src_ip'])
        
        self.send_pkt_msg(datapath, port, pkt.data)

    def handle_ndp_rs(self, dp, in_port, data):
        
        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is NDP RS packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.add_link_to_database(data['src_mac'], dp.id, 0, in_port)
        self.add_link_to_database(dp.id, data['src_mac'], in_port, 0)

    def handle_mld_report(self, dp, in_port, data):

        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        if (data['src_ip'] == '::'):
            print(f"data: {data}")
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is MLD packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.add_link_to_database(data['src_mac'], dp.id, 0, in_port)
        self.add_link_to_database(dp.id, data['src_mac'], in_port, 0)
    
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
    
    def delete_flow(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        for dst in self.mac_to_port[datapath.id].keys():
            match = parser.OFPMatch(eth_dst=dst)
            mod = parser.OFPFlowMod(
                datapath, command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                priority=1, match=match)
            datapath.send_msg(mod)
    
    def send_pkt_msg(self, datapath, port, data):
        
        parser = datapath.ofproto_parser
        
        out = parser.OFPPacketOut(
            datapath = datapath,
            buffer_id = ofproto_v1_5.OFP_NO_BUFFER,
            match = parser.OFPMatch(in_port=ofproto_v1_5.OFPP_CONTROLLER),
            actions = [parser.OFPActionOutput(port)],
            data=data)
        
        datapath.send_msg(out)

    def add_link_to_database(self, u, v, u_port_no, v_port_no):
        self.topo.set_link(u, v, u_port_no, v_port_no)
        # 只有 host 會使用 mac，需要自己換成好用的單位
        # switch 則使用 dpip，故只要是 mac addr，都會是 host
        if self.topo.is_mac(u):
            u = self.topo.get_hostName_from_mac(u)
        if self.topo.is_mac(v):
            v = self.topo.get_hostName_from_mac(v)
        self.networkGraph.add_link(u, v)
        # 這裡因為用在 mininet 上，使用 veth pair 網卡，
        # 用 traffic control 做流量控制，
        # 故我們是去偵測 tc 下面的資料，而不是 switch port 物理網卡資料
        bw = 0
        if not self.topo.is_host(u):
            bw = self.get_switch_port_bandwidth(u, u_port_no)
        else:
            bw = self.get_switch_port_bandwidth(v, v_port_no)
        
        self.topo.set_link_bandwidth(u, v, bw)
    
    def del_link_to_database(self, u, v=None):
        if self.topo.is_mac(u):
            u = self.topo.get_hostName_from_mac(u)
        if self.topo.is_mac(v):
            v = self.topo.get_hostName_from_mac(v)
        self.topo.del_link(u, v)
        self.topo.del_link_bandwidth(u, v)
        if v is not None:
            self.networkGraph.del_link(u, v)
        else:
            self.networkGraph.del_node(u)
        
    
    def get_switch_port_bandwidth(self, sw, port):
        interface = f"s{sw}-eth{port}"
        cmd = f"tc -s class show dev {interface}"
        result = os.popen(cmd).read()
        match = re.search(r"rate (\d+)Mbit ceil (\d+)Mbit", result)
        # 單位 Mbits
        if match:
            rate, ceil = match.groups()
            return ceil
        else:
            return None
    
    def write_path_to_switch(self, src, dst, ip_proto=None):
        
        path, length = self.networkGraph.dijkstra(src, dst)
        next_hop = self.networkGraph.get_next_hop(path)

        start_ipv6 = self.topo.get_host_single_ipv6(src)
        dest_ipv6 = self.topo.get_host_single_ipv6(dst)

        self.logger.info(f'  start src:{src}, start_ip: {start_ipv6}')
        self.logger.info(f'        dst:{dst}, dst_ip: {dest_ipv6}')

        self.logger.info(f'  Start writing rule to switch  ')
        for sw in path[1:-1]:
            next = next_hop[sw]

            port_u, port_v = self.topo.get_link(sw, next)
            dp = self.topo.get_datapath(sw)

            parser = dp.ofproto_parser
            match_ipv6 = self.set_OFPMatch(parser, start_ipv6, dest_ipv6, ip_proto=ip_proto)

            actions = [parser.OFPActionOutput(port_u)]
            self.logger.info(f'      Writing rule in switch: {dp.id}')
            self.add_flow(dp, 10, match_ipv6, actions)
        
        return path
    
    def set_OFPMatch(self, parser, ipv6_src, ipv6_dst, ip_proto=None):
        if ip_proto is None:
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IPV6,
                ipv6_src=ipv6_src,
                ipv6_dst=ipv6_dst
            )
        else:
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IPV6,
                ipv6_src=ipv6_src,
                ipv6_dst=ipv6_dst,
                ip_proto=ip_proto
            )
        return match
    
    def _monitor(self):
        """ 每 2 秒查詢一次 switch 的 port 統計資訊 """
        while True:
            self.topo.print_hosts()
            self.topo.print_links()
            self.topo.print_datapath()
            print(f'------------------------------')
            hub.sleep(2) 

    def _topo_monitor(self):
        """ 持續檢查特殊狀況 """
        while True:
            hub.sleep(5)  # 每 5 秒檢查一次
            if not self.topo.get_datapaths():  # 如果沒有交換機，執行 initialize()
                self.initialize()

            # 檢查是否需要取得 link bw 資訊
            if len(self.topo.get_links()) > 0:
                links = self.topo.get_links()
                for u, v in links:
                    if self.topo.get_link_bandwidth(u, v) is None:
                        u_port, v_port = links[(u, v)]
                        bw = 0
                        if not self.topo.is_host(u):
                            bw = self.get_switch_port_bandwidth(u, u_port)
                        else:
                            bw = self.get_switch_port_bandwidth(v, v_port)
                        
                        self.topo.set_link_bandwidth(u, v, bw)
