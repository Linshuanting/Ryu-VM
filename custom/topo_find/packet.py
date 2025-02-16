from ryu.ofproto import inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import lldp
from ryu.lib.packet import ipv6, icmpv6
from ryu.exception import RyuException

from ryu.lib.dpid import dpid_to_str
import copy, struct

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

