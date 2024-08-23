from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3, ofproto_v1_0, ofproto_v1_2
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
import os
class SimpleSwitch(app_manager.RyuApp):

    # 選擇支援的openFlow版本，可不只一個版本
    # OFP_VERSION = [ofproto_v1_3.OFP_VERSION]
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION, ofproto_v1_2.OFP_VERSION, ofproto_v1_3.OFP_VERSION]


    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.counter = {}
        self.mac_to_port = {}


    @set_ev_cls(ofp_event.EventOFPHello, HANDSHAKE_DISPATCHER)
    def _hello_handler(self, ev):
        self.logger.debug('OFPHello received, the ev.msg contains : ', ev.msg)
        msg = ev.msg
        
        datapath = msg.datapath
        port = str(datapath.address[0]) + ":" + str(datapath.address[1])
        
        if port in self.counter :
            self.counter[port] = self.counter[port] + 1
        else:
            self.counter.setdefault(port, 1)
        
        os.system('clear')

        print("\n--- print OFPHello info ---")
        print("msg", msg)
        print("datapath: ", datapath)
        print("datapath.supported_ofp_version :", datapath.supported_ofp_version)
        print("datapath.ofproto.OFP_VERSION", datapath.ofproto.OFP_VERSION)
        print("datapath.address", datapath.address, ", the IP try to connect", self.counter[port], "times.")
        print("msg.version", msg.version)
        print("---  OFPHello info end  ---")

        print("\n--- The IP address record ---")

        for i in self.counter:
            print(f'{i} : {self.counter[i]} time')
        
        print("--- IP address record end ---")

