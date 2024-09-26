'''
This is a group table which type is "OFPGT_SELECT" only supported in OPENFLOW15 and newer.
A new Netronome group experimenter property for selection method
Using select method argument "hash" or "dp_hash" to set this class 

You can check argument in ofproto_v1_5.py, key word is "oxm_types"
Using format f"OXM_OF_{oxm_types}" to set fields, remember using UPPERCASE_LETTER
fields argument example{
Flow labels: OXM_OF_IPV6_FLABEL,
IPv6 source: OXM_OF_IPV6_SRC,
Ethernet destination: OXM_OF_ETH_DST 
}

Notice: "dp_hash" does not support fields

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
                  exp_type=NTRT_SELECTION_METHOD, selection_method="hash",
                  selection_method_param=0, fields=None):
        super(OFPGroupPropExperimenter, self).__init__(type_, length)
        self.experimenter = experimenter # Netronome Vendor ID
        self.exp_type = exp_type # NTRT_SELECTION_METHOD
        self.selection_method = selection_method
        self.selection_method_param = selection_method_param
        self.fields = fields if fields else []  # field_array

    @classmethod
    def parser(cls, buf, offset=0):
        prop = cls()
        (prop.type, prop.length, prop.experimenter, prop.exp_type, selection_method_bytes, prop.selection_method_param) = struct.unpack_from(
            OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, buf, offset)
        prop.selection_method = selection_method_bytes.decode('ascii').strip(b'\x00')
        
        fields_len = (prop.length - OFP_GROUP_PROP_EXPERIMENTER_SIZE) // 4
        prop.fields = [struct.unpack_from('!I', buf, offset + i * 4)[0] for i in range(fields_len)]

        
        return prop

    def serialize(self):
        buf = bytearray()
        method_encoded = self.selection_method.encode('ascii').ljust(NTR_MAX_SELECTION_METHOD_LEN, b'\x00')
        print(f"Encoded method: {method_encoded}")
        
        # 序列化 fields
        fields_data = bytearray()
        for field in self.fields:
            msg_pack_into('!I', fields_data, len(fields_data), field)
        
        print(f"field buf: {fields_data.hex()}")

        # 计算总长度并填充
        self.length = OFP_GROUP_PROP_EXPERIMENTER_SIZE + len(fields_data)
        padding_length = (8 - (self.length % 8)) % 8
        self.length += padding_length

        msg_pack_into(OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, 
                      buf, 0, self.type, self.length, 
                      self.experimenter, self.exp_type,
                      method_encoded, self.selection_method_param)
        
        buf.extend(fields_data)

        # 追加 padding
        if padding_length > 0:
            buf.extend(b'\xff' * padding_length)

        print(f"The packet: {buf.hex()}")

        return buf
