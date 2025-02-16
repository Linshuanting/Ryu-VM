from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_5
from ryu.ofproto import inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import lldp
from ryu.lib.packet import ipv6, icmpv6
from ryu.lib import hub
from ryu.exception import RyuException
from topo_data_structure import Topology
from ryu.app.wsgi import WSGIApplication
import threading



from ryu.topology import event
# Below is the library used for topo discovery
from ryu.topology.api import get_switch, get_link, get_host
import copy, struct
from ryu.lib.dpid import dpid_to_str, str_to_dpid

class SimpleSwitch15(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    # _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch15, self).__init__(*args, **kwargs)
        self.topo = Topology()
        self.monitor_thread = hub.spawn(self._monitor)
        # self.lldp_thread = hub.spawn(self.lldp_sender)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        
        self.logger.info('OFPSwitchFeatures received: '
                         '\n\tdatapath_id=0x%016x n_buffers=%d '
                         '\n\tn_tables=%d auxiliary_id=%d '
                         '\n\tcapabilities=0x%08x',
                         msg.datapath_id, msg.n_buffers, msg.n_tables,
                         msg.auxiliary_id, msg.capabilities)
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        print(f'*** below is datapath_id:{datapath.id}')
        print(f'This is datapath:{datapath}')

        self.topo.set_datapath(datapath)
        
        self.send_port_request()
    
    # We are not using this function
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

    def send_pkt_msg(self, datapath, port, data):
        
        parser = datapath.ofproto_parser
        
        out = parser.OFPPacketOut(
            datapath = datapath,
            buffer_id = ofproto_v1_5.OFP_NO_BUFFER,
            match = parser.OFPMatch(in_port=ofproto_v1_5.OFPP_CONTROLLER),
            actions = [parser.OFPActionOutput(port)],
            data=data)
        
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _lldp_packet_in_handler(self, ev):
        
        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg)
        except LLDPPacket.LLDPUnknownFormat as e:
            return
        
        dst_dpid = msg.datapath.id
        dst_port_no = msg.match['in_port']

        print(f'***** Get the lldp packet in switch {dst_dpid}, port:{dst_port_no} from switch {src_dpid}, port:{src_port_no} ')

        self.topo.set_link(src_dpid, dst_dpid, src_port_no, dst_port_no)

        print(f"------ switch {dst_dpid} -----------")
        self.topo.print_links()

    def send_lldp_out(self, datapath, port):
        
        print(f'**** send the lldp packet in switch {datapath.id}, port:{port}')
        data = LLDPPacket.lldp_packet(datapath.id, port)
        self.send_pkt_msg(datapath, port, data)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def _port_status_handler(self,ev):
        
        msg=ev.msg
        dp=msg.datapath
        body=ev.msg.body

        # print(f"body: {body}")
        
        for p in body:
            print(f'** switch {dp.id} get the PortDesc in Port:{p.port_no}')
            if p.port_no != ofproto_v1_5.OFPP_CONTROLLER and p.port_no != ofproto_v1_5.OFPP_LOCAL:
                # self.topo.set_port_in_switch(dp.id, p.port_no)
                self.topo.set_sw_mac_to_context(p.hw_addr, dp.id, p.port_no)
                self.topo.set_datapath(dp, dp.id)
                self.topo.del_link(p.hw_addr)
                self.topo.del_host(p.hw_addr)
                self.send_lldp_out(dp, p.port_no)
            else:
                print(f'*** skip the PortDesc in Port:{p.port_no}')
        
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
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
            print("--- This is MLDv2 report ---")
            print(data)
            self.handle_mld_report(dp, in_port, data)
            return
        
    def send_icmpv6_request(self, datapath, port, switch_port_mac, switch_port_ip):
        data = Icmpv6Packet.icmpv6_request_packet(switch_port_mac, switch_port_ip)
        self.send_pkt_msg(datapath, port, data)

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
        self.topo.set_link(data['src_mac'], dp.id, 0, in_port)
        self.topo.set_link(dp.id, data['src_mac'], in_port, 0)

    def handle_ndp_ns(self, dp, in_port, data):

        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is NDP NS packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.topo.set_link(data['src_mac'], dp.id, 0, in_port)
        self.topo.set_link(dp.id, data['src_mac'], in_port, 0)
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
        # print(f"pkt: {pkt}")
        self.send_pkt_msg(datapath, port, pkt.data)

    def handle_ndp_rs(self, dp, in_port, data):
        
        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is NDP RS packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.topo.set_link(data['src_mac'], dp.id, 0, in_port)
        self.topo.set_link(dp.id, data['src_mac'], in_port, 0)

    def handle_mld_report(self, dp, in_port, data):

        if (self.topo.contain_host(mac=data['src_mac']) is False):
            return
        if (data['src_ip'] == '::'):
            print(f"data: {data}")
            return
        
        print(f'*===== This is in switch {dp.id} =====')
        print(f'** This is MLD packet, the src_mac:{data["src_mac"]}, the src_ip:{data["src_ip"]}')
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.topo.set_link(data['src_mac'], dp.id, 0, in_port)
        self.topo.set_link(dp.id, data['src_mac'], in_port, 0)
    
    def _monitor(self):
        """ 每 2 秒查詢一次 switch 的 port 統計資訊 """
        while True:
            self.topo.print_hosts()
            self.topo.print_links()
            self.topo.print_datapath()
            print(f'------------------------------')
            hub.sleep(2) 
    
    def lldp_sender(self):
        
        while True:
            hub.sleep(3)
            for dp_id, dp in self.topo.get_datapaths().items():
                for port_no, port in dp.ports.items():
                    self.send_lldp_out(dp, port_no)
            
    
    def send_port_request(self):
        def delayed_execution():
            for dp_id, datapath in self.topo.get_datapaths().items():
                print(f'*** below is datapath_id:{dp_id}')
                print(f'This is datapath:{dp_id}')
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser

                msg = parser.OFPPortDescStatsRequest(datapath)
                print(msg)
                datapath.send_msg(msg)

        # 啟動一個計時器，0 秒後執行 delayed_execution
        threading.Timer(3, delayed_execution).start()



class Icmpv6Packet(object):

    class Icmpv6UnknownFormat(RyuException):
        message = '%(msg)s'

    @staticmethod
    def icmpv6_parse(msg):

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        ip6 = pkt.get_protocol(ipv6.ipv6)
        icmpv6_pkt = pkt.get_protocol(icmpv6.icmpv6)

        if icmpv6_pkt is None:
            raise Icmpv6Packet.Icmpv6UnknownFormat()
        
        src_mac = eth.src
        src_ip = ip6.src
        dst_ip = ip6.dst

        if icmpv6_pkt.type_ == icmpv6.ICMPV6_ECHO_REPLY:
            return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'icmpv6_type': icmpv6.ICMPV6_ECHO_REPLY,
            }
        
         # 檢查是否是 Neighbor Solicitation (NS) 或 Neighbor Advertisement (NA)
        if icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_SOLICIT or icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_ADVERT:
            ndp_type = icmpv6_pkt.type_  # 獲取 NDP 消息類型（NS 或 NA）
            target_ip = icmpv6_pkt.data.dst  # 鄰居廣告/請求的目標地址
            # 回傳解析的結果
            return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'icmpv6_type': ndp_type,
                'target_ip': target_ip,
            }
        
        if icmpv6_pkt.type_==icmpv6.ND_ROUTER_SOLICIT or icmpv6_pkt.type_ == icmpv6.ND_ROUTER_ADVERT:
            ndp_type = icmpv6_pkt.type_
            return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'icmpv6_type': ndp_type,
            }
        
        # RS, RA
        # MLDv2
        return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'icmpv6_type': icmpv6_pkt.type_,
            }

    @staticmethod
    def icmpv6_request_packet(src_mac, src_ip):
        # 創建 Ethernet 頭
        eth = ethernet.ethernet(dst='33:33:00:00:00:01',
                                src=src_mac,
                                ethertype=ether_types.ETH_TYPE_IPV6)
        # 創建 IPv6 頭，目的地址是所有節點的多播地址
        ipv6_pkt = ipv6.ipv6(src=src_ip, dst='ff02::1', nxt=inet.IPPROTO_ICMPV6)
        # 創建 ICMPv6 Echo Request 封包
        echo_request = icmpv6.icmpv6(type_=icmpv6.ICMPV6_ECHO_REQUEST, code=0)

        # 封裝成完整封包
        pkt = packet.Packet()
        pkt.add_protocol(eth)
        pkt.add_protocol(ipv6_pkt)
        pkt.add_protocol(echo_request)
        pkt.serialize()

        return pkt

class NDPPacket(object):

    class NDPUnknownFormat(RyuException):
        message = '%(msg)s'

    @staticmethod
    def ndp_parse(msg):
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        ip6 = pkt.get_protocol(ipv6.ipv6)
        icmpv6_pkt = pkt.get_protocol(icmpv6.icmpv6)

        if ip6 is None:
            # print("ndp ipv6 is None")
            raise NDPPacket.NDPUnknownFormat()

        if  icmpv6_pkt is None:
            # print("ndp icmpv6 is None")
            raise NDPPacket.NDPUnknownFormat()
        
        # 提取以太網幀中的源 MAC 地址
        src_mac = eth.src

        # 提取 IPv6 標頭中的源地址和目的地址
        src_ip = ip6.src
        dst_ip = ip6.dst

         # 檢查是否是 Neighbor Solicitation (NS) 或 Neighbor Advertisement (NA)
        if icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_SOLICIT or icmpv6_pkt.type_ == icmpv6.ND_NEIGHBOR_ADVERT:
            ndp_type = icmpv6_pkt.type_  # 獲取 NDP 消息類型（NS 或 NA）
            target_ip = icmpv6_pkt.data.dst  # 鄰居廣告/請求的目標地址
            # 回傳解析的結果
            return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'ndp_type': ndp_type,
                'target_ip': target_ip,
            }
        
        if icmpv6_pkt.type_==icmpv6.ND_ROUTER_SOLICIT or icmpv6_pkt.type_ == icmpv6.ND_ROUTER_ADVERT:
            ndp_type = icmpv6_pkt.type_
            return {
                'src_mac': src_mac,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'ndp_type': ndp_type,
            }
        
        return None
    
    @staticmethod
    def ndp_packet(type, src_mac, dst_mac, src_ip, dst_ip):

        if type == icmpv6.ND_NEIGHBOR_SOLICIT:
            eth = ethernet.ethernet(dst='33:33:ff:00:00:00',
                                src=src_mac,
                                ethertype=ether_types.ETH_TYPE_IPV6)

            ipv6_pkt = ipv6.ipv6(src=src_ip,
                                dst='ff02::1:ff' + dst_ip[-6:],  # 多播地址
                                nxt=inet.IPPROTO_ICMPV6)
            
            # 創建 ICMPv6 Neighbor Solicitation 封包
            ndp_pkt = icmpv6.nd_neighbor(res=0,
                                        dst=dst_ip)
            icmpv6_pkt = icmpv6.icmpv6(
                type_=icmpv6.ND_NEIGHBOR_SOLICIT, 
                data=ndp_pkt)
            
        elif type == icmpv6.ND_NEIGHBOR_ADVERT:
            eth = ethernet.ethernet(dst=dst_mac,
                                src=src_mac,
                                ethertype=ether_types.ETH_TYPE_IPV6)
            ipv6_pkt = ipv6.ipv6(src=src_ip,
                                dst=dst_ip,
                                nxt=inet.IPPROTO_ICMPV6)
            ndp_pkt = icmpv6.nd_neighbor(
                res=6, 
                dst=src_ip,
                option=icmpv6.nd_option_tla(hw_src=src_mac))
            icmpv6_pkt = icmpv6.icmpv6(
                type_=icmpv6.ND_NEIGHBOR_ADVERT, 
                data=ndp_pkt)

        # 將封包封裝
        pkt = packet.Packet()
        pkt.add_protocol(eth)
        pkt.add_protocol(ipv6_pkt)
        pkt.add_protocol(icmpv6_pkt)

        pkt.serialize()

        return pkt

class LLDPPacket(object):

    CHASSIS_ID_PREFIX = 'dpid:'
    CHASSIS_ID_PREFIX_LEN = len(CHASSIS_ID_PREFIX)
    CHASSIS_ID_FMT = CHASSIS_ID_PREFIX + '%s'

    PORT_ID_STR = '!I'      # uint32_t
    PORT_ID_SIZE = 4

    class LLDPUnknownFormat(RyuException):
        message = '%(msg)s'

    @staticmethod
    def lldp_parse(msg):
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype != ether_types.ETH_TYPE_LLDP:
            raise LLDPPacket.LLDPUnknownFormat()

        lldp_header = pkt.get_protocol(lldp.lldp)

        tlv_chassis = lldp_header.tlvs[0]
        tlv_port = lldp_header.tlvs[1]
        
        chassis_id_str = tlv_chassis.chassis_id.decode('utf-8')
        src_dpid = 0
        if chassis_id_str.startswith('dpid:'):
            # 提取數字部分並轉換為整數
            src_dpid = int(chassis_id_str.split(':')[1], 16)    # 以16進制轉換

        src_port = 0
        if hasattr(tlv_port, 'port_id') and tlv_port.port_id:
            port_id_value = int.from_bytes(tlv_port.port_id, byteorder='big')
            print(f"port_id_value: {port_id_value}")
            src_port = port_id_value
        else:
            print("port_id is missing or empty.")
            src_port = 0 

        return src_dpid, src_port
    
    @staticmethod
    def lldp_packet(dpid, port, src_maddr=lldp.LLDP_MAC_NEAREST_BRIDGE, ttl=5):
        pkt = packet.Packet()

        dst = lldp.LLDP_MAC_NEAREST_BRIDGE
        src = src_maddr
        ethertype = ether_types.ETH_TYPE_LLDP
        eth_pkt = ethernet.ethernet(dst, src, ethertype)
        pkt.add_protocol(eth_pkt)

        tlv_chassis_id = lldp.ChassisID(
            subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED,
            chassis_id=(LLDPPacket.CHASSIS_ID_FMT %
                        dpid_to_str(dpid)).encode('ascii'))

        tlv_port_id = lldp.PortID(subtype=lldp.PortID.SUB_PORT_COMPONENT,
                                  port_id=struct.pack(
                                      LLDPPacket.PORT_ID_STR,
                                      port))

        tlv_ttl = lldp.TTL(ttl=ttl)
        tlv_end = lldp.End()

        tlvs = (tlv_chassis_id, tlv_port_id, tlv_ttl, tlv_end)
        lldp_pkt = lldp.lldp(tlvs)
        pkt.add_protocol(lldp_pkt)

        pkt.serialize()

        # print(f"send LLdp switch:{dpid}, port:{port}")

        return pkt.data

