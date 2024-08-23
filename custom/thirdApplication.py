from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0, ofproto_v1_2, ofproto_v1_3

from enum import Enum
import os

class connectStatus(Enum):
    up = 1
    down = 0

class L2Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION, ofproto_v1_2.OFP_VERSION, ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(L2Switch, self).__init__(*args, **kwargs)
        self.counter = {}
        self.status = {}

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
            self.status.setdefault(port, connectStatus.up)
        
        os.system('clear')
        print("\n--- print OFPHello info ---")
        print("msg", msg)
        print("datapath.supported_ofp_version :", datapath.supported_ofp_version)
        print("datapath.ofproto.OFP_VERSION", datapath.ofproto.OFP_VERSION)
        print("datapath.address", datapath.address, ", the IP try to connect", self.counter[port], "times.")
        print("msg.version", msg.version)
        print("---  OFPHello info end  ---")
        self.connectStatus()


    @set_ev_cls(ofp_event.EventOFPStateChange, DEAD_DISPATCHER)
    def disconnect_handler(self, ev):
        datapath = ev.datapath
        port = str(datapath.address[0]) + ":" + str(datapath.address[1])
        self.status[port] = connectStatus.down
        print("\n--- print OFPStateChange info ---")
        print(datapath.address, "disconnected.")
        print("---  OFPHello OFPStateChange end  ---")
        self.connectStatus()

    def connectStatus(self):
        print("\n--- The IP address record ---")

        for i in self.counter:
            status = 'connected' if self.status[i] == connectStatus.up else 'disconnected'
            print(f'{i} : {self.counter[i]} time, {status}')
        
        print("---  IP address record end  ---")
        