from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3

class SimpleSwitch(app_manager.RyuApp):
    
    # 選擇支援的openFlow版本，可不只一個版本
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        
        # super().__init__會去呼叫父類別的initializer__init__
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        
