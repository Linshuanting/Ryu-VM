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



from packet import Icmpv6Packet, NDPPacket, LLDPPacket

class TopoFind(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopoFind, self).__init__(*args, **kwargs)
        self.topo = Topology()
        self.monitor_thread = hub.spawn(self._monitor) 

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

        self.topo.set_datapath(datapath)

        portRequestmsg = parser.OFPPortDescStatsRequest(datapath)
        datapath.send_msg(portRequestmsg)
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _lldp_packet_in_handler(self, ev):
        
        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg)
        except LLDPPacket.LLDPUnknownFormat as e:
            return
        
        dst_dpid = msg.datapath.id
        dst_port_no = msg.match['in_port']

        self.logger.info(f'***** Get the lldp packet in switch {dst_dpid}, port:{dst_port_no} from switch {src_dpid}, port:{src_port_no} ')

        self.topo.set_link(src_dpid, dst_dpid, src_port_no, dst_port_no)

        print(f"------ switch {dst_dpid} -----------")
        self.topo.print_links()
    
    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def _port_status_handler(self,ev):
        
        msg=ev.msg
        dp=msg.datapath
        body=ev.msg.body
        
        for p in body:
            self.logger.info(f'** switch {dp.id} get the PortDesc in Port:{p.port_no}')
            if p.port_no != ofproto_v1_5.OFPP_CONTROLLER and p.port_no != ofproto_v1_5.OFPP_LOCAL:
                # self.topo.set_port_in_switch(dp.id, p.port_no)
                self.topo.set_sw_mac_to_context(p.hw_addr, dp.id, p.port_no)
                self.topo.set_datapath(dp, dp.id)
                self.send_lldp_out(dp, p.port_no)
            else:
                self.logger.info(f'*** skip the PortDesc in Port:{p.port_no}')

    def send_lldp_out(self, datapath, port):
        
        self.logger.info(f'**** send the lldp packet in switch {datapath.id}, port:{port}')
        data = LLDPPacket.lldp_packet(datapath.id, port)
        self.send_pkt_msg(datapath, port, data)

    def _monitor(self):
        """ 每 2 秒查詢一次 switch 的 port 統計資訊 """
        while True:
            self.topo.print_hosts()
            self.topo.print_links()
            self.topo.print_datapath()
            print(f'------------------------------')
            hub.sleep(2) 
    
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