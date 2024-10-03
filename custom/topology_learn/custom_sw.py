from ryu.ofproto import ofproto_v1_5
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ofproto_v1_4
from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.topology import event, switches
from ryu.topology.api import get_link, get_host, get_switch

class CustomSwitches(switches.Switches):
    # 覆寫 OFP_VERSIONS 屬性，添加 OpenFlow 1.5 支持
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION,
                    ofproto_v1_2.OFP_VERSION,
                    ofproto_v1_3.OFP_VERSION,
                    ofproto_v1_4.OFP_VERSION,
                    ofproto_v1_5.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(CustomSwitches, self).__init__(*args, **kwargs)
        self.logger.info("CustomSwitches is initialized with OpenFlow versions: {}".format(self.OFP_VERSIONS))

    