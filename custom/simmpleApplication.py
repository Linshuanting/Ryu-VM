from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub

import time

class SimpleSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.port_stats = {}  # 記錄每個 port 的上次流量
        self.monitor_thread = hub.spawn(self._monitor)


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安裝默認流規則，將所有未知封包發送到控制器
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # 忽略LLDP封包
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # 記錄 MAC 位址到埠的映射
        self.mac_to_port[dpid][src] = in_port

        # 確定目標埠
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            # 如果未知，將封包發送到所有埠
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # 安裝流規則
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath, 1, match, actions)

        # 發送封包
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=msg.data)
        datapath.send_msg(out)
    
    @set_ev_cls(ofp_event.EventOFPStateChange, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def state_change_handler(self, ev):
        """ 當 switch 連接或斷線時，更新 datapaths """
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == CONFIG_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def _monitor(self):
        """ 每 2 秒查詢一次 switch 的 port 統計資訊 """
        while True:
            for dp in self.datapaths.values():
                self._request_port_stats(dp)
            hub.sleep(2)  # 設定查詢間隔（秒）

    def _request_port_stats(self, datapath):
        """ 向 switch 發送端口統計請求 """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        """ 處理 switch 回傳的端口統計資訊 """
        timestamp = time.time()
        for stat in ev.msg.body:
            port_no = stat.port_no
            tx_bytes = stat.tx_bytes  # 目前傳輸的總 bytes

            # 計算頻寬使用率 (bps)
            if (ev.msg.datapath.id, port_no) in self.port_stats:
                prev_tx_bytes, prev_time = self.port_stats[(ev.msg.datapath.id, port_no)]
                time_interval = timestamp - prev_time
                speed_bps = ((tx_bytes - prev_tx_bytes) * 8) / time_interval  # 轉為 bit/s
                speed_mbps = speed_bps / 1e6  # 轉為 Mbps
                self.logger.info(f"Switch {ev.msg.datapath.id} Port {port_no} Speed: {speed_mbps:.2f} Mbps")
            
            # 更新歷史數據
            self.port_stats[(ev.msg.datapath.id, port_no)] = (tx_bytes, timestamp)
        
        
    

