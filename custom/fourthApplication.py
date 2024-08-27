from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, packet
from log.log import MyLog

class SimpleSwitch(app_manager.RyuApp):

    # 選擇支援的openFlow版本，可不只一個版本
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    LOGGER_NAME = 'Forth_Application'
    LOG_PATH = f'./custom/log/{LOGGER_NAME}.log'

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        # 新增一個儲存 Host MAC 的資料結構，類別為 dict(字典)
        self.mac_to_port = {}
        self.log = MyLog(self.LOGGER_NAME, self.LOG_PATH)
        self.logger = self.log.get_logger()
        
        # test message
        self.logger.info("This is an info message.")
        self.logger.error("This is an error message.")
        

    @set_ev_cls(ofp_event.EventOFPHello, HANDSHAKE_DISPATCHER)
    def _hello_handler(self, ev):
        self.logger.debug('OFPHello received')
        print('OFPHello received')
    
    
    # Hint : pre-install a Table-miss flow entry after handshaking.
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

    def add_flow(self, datapath, priority, match, actions):

        # processing some informations.
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        inst = [ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        # Generate the OFPFlowMod message.
        mod = ofp_parser.OFPFlowMod(datapath = datapath, priority = priority, match = match, instructions = inst)

        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        
        # processing some infomations.
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # catch the ingress port.
        in_port = msg.match['in_port']

        # catch ethernet header (mac address header).
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # the "destination" means the destination mac address and "source" is the source mac address.
        destination = eth.dst
        source = eth.src
        
        # catch switch id.
        datapath_id = datapath.id
        self.mac_to_port.setdefault(datapath_id, {})

        self.logger.info("packet in %s %s %s %s", datapath_id, source, destination, in_port)

        # 將 port 與 switch 和 source mac address 的組合儲存起來。
        self.mac_to_port[datapath_id][source] = in_port

        # Gudge the desination MAC address is exist or not, if exist, deliverying the Flow Mod message and then add Flow entry in the switch.
        if destination in self.mac_to_port[datapath_id]:
                out_port = self.mac_to_port[datapath_id][destination]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [ofp_parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = ofp_parser.OFPMatch(in_port = in_port, eth_dst = destination, eth_src =source)
            self.add_flow(datapath, 1, match, actions)

        # devivery packet-out message.
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        output_data = ofp_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(output_data)