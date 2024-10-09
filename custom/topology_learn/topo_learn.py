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
from collections import defaultdict as ddict
from ryu.exception import RyuException
from sortedcontainers import SortedList


from ryu.topology import event
# Below is the library used for topo discovery
from ryu.topology.api import get_switch, get_link, get_host
import copy, struct
from ryu.lib.dpid import dpid_to_str, str_to_dpid

class SimpleSwitch15(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch15, self).__init__(*args, **kwargs)
        
        self.topo = Topology()

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

        msg = parser.OFPPortDescStatsRequest(datapath)
        datapath.send_msg(msg)

    
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
        except LLDPPacket.LLDPUnknownFormat:
            # This handler can receive all the packets which can be
            # not-LLDP packet. Ignore it silently
            return
        
        dst_dpid = msg.datapath.id
        dst_port_no = msg.match['in_port']

        self.topo.build_edge(src_dpid, src_port_no, dst_dpid, dst_port_no)

        print(f"------ switch {dst_dpid} -----------")
        self.topo.get_links()

    def send_lldp_out(self, datapath, port):
        
        data = LLDPPacket.lldp_packet(datapath.id, port)
        self.send_pkt_msg(datapath, port, data)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_status_handler(self,ev):
        
        msg=ev.msg
        dp=msg.datapath
        body=ev.msg.body

        # print(f"body: {body}")
        
        for p in body:
            if p.port_no != ofproto_v1_5.OFPP_CONTROLLER and p.port_no != ofproto_v1_5.OFPP_LOCAL:
                self.topo.set_port_in_switch(dp.id, p.port_no)
                self.topo.set_switch_port_mac(p.hw_addr, p.port_no, dp.id)
                self.send_lldp_out(dp, p.port_no)
                
    
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
        
        if (self.topo.is_switch_mac(data['src_mac'])):
            return

        if (self.topo.is_ip_is_used(data['target_ip']) 
            and data['target_ip'].startswith('ff') is False):
            # reply dad msg
            return
            
        self.topo.set_host(data['src_mac'], data['target_ip'], dp.id, in_port)
        self.topo.get_hosts()

    def handle_ndp_ns(self, dp, in_port, data):

        if (self.topo.is_host(data['src_mac']) is False):
            return
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.send_ndp_na_out(dp, in_port, data)

        self.topo.get_hosts()

    def send_ndp_na_out(self, datapath, port, data):
        
        src_mac = self.topo.get_mac_from_ip(data['target_ip'])
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
        
        if (self.topo.is_host(data['src_mac']) is False):
            return
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.topo.get_hosts()

    def handle_mld_report(self, dp, in_port, data):

        if (self.topo.is_host(data['src_mac']) is False):
            return
        if (data['src_ip'] == '::'):
            print(f"data: {data}")
            return
        
        self.topo.set_host(data['src_mac'], data['src_ip'], dp.id, in_port)
        self.topo.get_hosts()

class Topology(dict):

    P_DOWN = None
    P_UP = 1

    def __init__(self):

        # 紀錄 switch 上的所有 ports
        self.switchports=ddict(dict)
        # 紀錄兩個 switch 之間的連接 
        self.links = ddict(dict)
        self.mac_to_port=ddict(dict)
        # 紀錄 switch mac_addres 對應的 switch_id 
        self.datapaths = ddict(dict)
        # 紀錄 host mac_address, host_ip, 以及其對應連接的 switch_id, switch_port
        self.hosts = ddict(dict)
        

    def set_host(self, host_mac, host_ip, sw_id, sw_in_port):
        # 如果該 MAC 地址已存在，將新的 IP 地址添加到列表中
        if host_mac in self.hosts:
            # 檢查 IP 是否已經在列表中，如果沒有，則添加
            if host_ip not in self.hosts[host_mac]['ips']:
                self.hosts[host_mac]['ips'].add(host_ip)
        else:
            # 如果該 MAC 地址不存在，則創建新的條目
            self.hosts[host_mac] = {
                'ips': SortedList([host_ip]),  # 使用列表來存儲多個 IP
                'sw_id': sw_id,
                'sw_in_port': sw_in_port
            }

    def get_host(self, host_mac):
        if host_mac in self.hosts:
            return self.hosts[host_mac]
        return None
    
    def get_hosts(self):
        print("------ Get all hosts -------")
        for host_mac, host_info in self.hosts.items():  # host_info 是元組
            print(f"host mac: {host_mac}, host ips: {host_info['ips']}, switch id: {host_info['sw_id']}, switch port: {host_info['sw_in_port']}")

    def is_host(self, mac):
        if mac in self.hosts:
            return True
        return False
    
    def is_ip_is_used(self, ip):
        for host_mac, host_info in self.hosts.items():
            for host_ip in host_info['ips']:
                if ip == host_ip:
                    return True
        return False
    
    def get_mac_from_ip(self, ip):
        for host_mac, host_info in self.hosts.items():
            for host_ip in host_info['ips']:
                if ip == host_ip:
                    return host_mac
        return None
    
    def get_ports_in_switch(self, dp):
        if dp in self.switchports:
            return [port for port in self.switchports[dp]]
        return []
    
    def set_switch_port_mac(self, mac, port, dp):
        self.datapaths[mac]= (dp, port)
    
    def get_switch_port_mac(self, mac):
        pass

    def is_switch_mac(self, mac):
        return mac in self.datapaths

    def set_port_in_switch(self, dp, port):
        self.switchports[dp][port]= Topology.P_UP

    def is_port_in_switch(self, dp, port):
        return dp in self.switchports and port in self.switchports[dp]

    def build_edge(self, src_id, src_port, dst_id, dst_port):
        self.links[src_id][dst_id] = src_port, dst_port

    def _is_link(self, src_id, dst_id):
        if src_id in self.links and dst_id in self.links[src_id]:
            return self.links[src_id][dst_id]
        return None
    
    def remove_edge(self, src_id, dst_id):
        if src_id in self.links and dst_id in self.links[src_id]:
            del self.links[src_id][dst_id]
        # 如果 links[src_id] 已經沒有其他鏈接，可以選擇刪除它
        if not self.links[src_id]:
            del self.links[src_id]

    def get_links(self):
        all_links = []
        for src_id, dsts in self.links.items():
            for dst_id, ports in dsts.items():
                # 端口信息是 (src_port, dst_port)
                src_port, dst_port = ports
                # 將鏈接信息添加到 all_links 列表
                all_links.append((src_id, src_port, dst_id, dst_port))
                print(f"src:{src_id}, dst:{dst_id}")
                print(f"src port:{src_port}, dst port:{dst_port}")
        return all_links

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

        port_id_str = tlv_port.port_id.decode('utf-8')
        src_port = 0
        if port_id_str.startswith('port:'):
            src_port = int(port_id_str.split(':')[1])  

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

