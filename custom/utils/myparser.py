'''
This is a group table which type is "OFPGT_SELECT"
A new Netronome group experimenter property for selection method
Using select method argument "hash" or "dp_hash" to set this class 



Reference: https://github.com/openvswitch/ovs/blob/main/Documentation/group-selection-method-property.txt
'''

from ryu.ofproto import ofproto_v1_5 as ofproto
from ryu.ofproto.ofproto_v1_5_parser import OFPGroupProp, OFPPropCommonExperimenter4ByteData
from ryu.lib.pack_utils import msg_pack_into
import struct

NTR_MAX_SELECTION_METHOD_LEN = 16
OFP_GROUP_PROP_EXPERIMENTER_PACK_STR = '!HHII4x16sQ'
OFP_GROUP_PROP_EXPERIMENTER_SIZE = 40  # Struct中的固定大小部分（24 bytes）+ selection_method(16 bytes)

NTRT_SELECTION_METHOD = 1
NETRONOME_VENDER_ID = 0x0000154d

@OFPGroupProp.register_type(ofproto.OFPGPT_EXPERIMENTER)
class OFPGroupPropExperimenter(OFPPropCommonExperimenter4ByteData):
    def __init__(self, type_=None, length=None, experimenter=NETRONOME_VENDER_ID,
                  exp_type=NTRT_SELECTION_METHOD, selection_method="hash", selection_method_param=0):
        super(OFPGroupPropExperimenter, self).__init__(type_, length)
        self.experimenter = experimenter # Netronome Vendor ID
        self.exp_type = exp_type # NTRT_SELECTION_METHOD
        self.selection_method = selection_method
        self.selection_method_param = selection_method_param

    @classmethod
    def parser(cls, buf, offset=0):
        prop = cls()
        (prop.type, prop.length, prop.experimenter, prop.exp_type, selection_method_bytes, prop.selection_method_param) = struct.unpack_from(
            OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, buf, offset)
        prop.selection_method = selection_method_bytes.decode('ascii').strip(b'\x00')
        return prop

    def serialize(self):
        buf = bytearray()
        method_encoded = self.selection_method.encode('ascii').ljust(NTR_MAX_SELECTION_METHOD_LEN, b'\x00')
        print(f"Encoded method: {method_encoded}")
        self.length = OFP_GROUP_PROP_EXPERIMENTER_SIZE  # 固定长度40字节
        msg_pack_into(OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, 
                      buf, 0, self.type, self.length, 
                      self.experimenter, self.exp_type,
                      method_encoded, self.selection_method_param)
        

        return buf
