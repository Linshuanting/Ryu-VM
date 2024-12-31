'''
This parser is for openFlow15 version, check the OpenFlow version in your code first.
This is a group table which type is "OFPGT_SELECT" only supported in OPENFLOW15 and newer.
A new Netronome group experimenter property for selection method
Using select method argument "hash" or "dp_hash" to set this class 

Because the field field needs OXM_Tlv format, I advised you to check the OpenFlow official document.
The hasmask value is needed as 0, and the value is needed all 1 bits for all ask.
You can check field argument in ofproto_v1_5_parser.py, key word is "OFPMATCH(StringifyMixin)"
You can add the argument in this python file, below has the common argument (from Line 85)
Fields argument need used "all 1 bits" format.
For example, 
    ipv6_flabel is 32 bits, and the argument for ivp6_flabel is 0xffffffff
    ipv4_src is 32 bits address, the argument for ipv4_src is "255.255.255.255s"

If you want to check the  

Notice: "dp_hash" does not support fields

Reference: https://github.com/openvswitch/ovs/blob/main/Documentation/group-selection-method-property.txt
'''

from ryu.ofproto import ofproto_v1_5 as ofproto
from ryu.ofproto.ofproto_v1_5_parser import OFPGroupProp, OFPPropCommonExperimenter4ByteData, OFPOxmId, OFPMatch
# from ryu.ofproto.ofproto_v1_3_parser import OFPMatch
from ryu.lib.pack_utils import msg_pack_into
from ryu import utils
from ryu.ofproto import oxm_fields
import struct


OFP_GROUP_PROP_EXPERIMENTER_PACK_STR = '!HHII4x16sQ'
OFP_GROUP_PROP_EXPERIMENTER_SIZE = 40  # 2+2+4+4+4+16+8

NETRONOME_VENDER_ID = 0x0000154d
NTRT_SELECTION_METHOD = 1
NTR_MAX_SELECTION_METHOD_LEN = 16
@OFPGroupProp.register_type(ofproto.OFPGPT_EXPERIMENTER)
class OFPGroupPropExperimenter(OFPPropCommonExperimenter4ByteData):
    def __init__(self, type_=None, length=None, experimenter=NETRONOME_VENDER_ID,
                  exp_type=NTRT_SELECTION_METHOD, selection_method=None, selection_method_param=0,
                  **kwargs):
        super(OFPGroupPropExperimenter, self).__init__(type_, length)
        self.experimenter = experimenter # Netronome Vendor ID
        self.exp_type = exp_type # NTRT_SELECTION_METHOD
        self.selection_method = selection_method
        self.selection_method_param = selection_method_param
        
        self.oxm_tlv = OXMTLV(**kwargs)

    @classmethod
    def parser(cls, buf, offset=0):
        prop = cls()
        (prop.type, prop.length, prop.experimenter, prop.exp_type, selection_method_bytes, prop.selection_method_param) = struct.unpack_from(
            OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, buf, offset)
        prop.selection_method = selection_method_bytes.decode('ascii').strip(b'\x00')
        
        fields_len = (prop.length - OFP_GROUP_PROP_EXPERIMENTER_SIZE) // 4
        # prop.fields = [struct.unpack_from('!I', buf, offset + i * 4)[0] for i in range(fields_len)]
        
        return prop

    def serialize(self):
        buf = bytearray()
        method_encoded = self.selection_method.encode('ascii').ljust(NTR_MAX_SELECTION_METHOD_LEN, b'\x00')
        # print(f"Encoded method: {method_encoded}")
        
        # 使用 oxm_fields 來自動處理 OXM 字段的序列化
        # 這裡的 field_len 不包含 field padding，非常重要
        fields_data = bytearray()
        field_len = self.oxm_tlv.serialize(fields_data, 0)

        self.length = OFP_GROUP_PROP_EXPERIMENTER_SIZE + field_len

        msg_pack_into(OFP_GROUP_PROP_EXPERIMENTER_PACK_STR, 
                      buf, 0, self.type, self.length, 
                      self.experimenter, self.exp_type,
                      method_encoded, self.selection_method_param)
        
        buf.extend(fields_data)

        # print(f"buffer length: {len(buf)}, buffer: {buf.hex()}")

        return buf
    
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_FLABEL = 0xffffffff
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_SRC = "FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF"
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_DST = "FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF"
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV4_SRC = "255.255.255.255"
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV4_DST = "255.255.255.255"
OFP_GROUP_PROP_FIELD_MATCH_ALL_ETH_SRC = "FF:FF:FF:FF:FF:FF"
OFP_GROUP_PROP_FIELD_MATCH_ALL_ETH_DST = "FF:FF:FF:FF:FF:FF"
OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_EXTHDR = 0xffff

class OXMTLV():
    def __init__(self, type_=None, length=None,**kwargs) -> None:
        
        self.length = length

        if not kwargs:
            print("kwargs is zero")
            fields = []
            return

        kwargs = dict(ofproto.oxm_normalize_user(k, v) for
                          (k, v) in kwargs.items())
        fields = [ofproto.oxm_from_user(k, v) for (k, v)
                      in kwargs.items()]
        # assumption: sorting by OXM type values makes fields
        # meet ordering requirements (eg. eth_type before ipv4_src)
        fields.sort(
                key=lambda x: x[0][0] if isinstance(x[0], tuple) else x[0])
        self._fields = [ofproto.oxm_to_user(n, v, m) for (n, v, m)
                             in fields]
        
    @classmethod
    def parser(cls, buf, offset):
        print("parser is not finish")

    def serialize(self, buf, offset):

        fields = [ofproto.oxm_from_user(k, uv) for (k, uv)
                  in self._fields]

        field_offset = offset
        for name, value, mask in fields:
            field_offset += ofproto.oxm_serialize(name, value, mask, buf, field_offset)
            
        length = field_offset-offset
        # print(f"Serialized data (hex): {buf.hex()}")
        # print(f"Serialized length: {length} bytes")
        self.length = length

        pad_len = utils.round_up(length, 8) - length
        msg_pack_into("%dx" % pad_len, buf, field_offset)

        # print(f"field length: {length+pad_len}")  
        
        return length
    
    def items(self):
        return self._fields
    
    def __getitem__(self, key):
        return dict(self._fields)[key]

    def __contains__(self, key):
        return key in dict(self._fields)
    
    def to_jsondict(self):
        """
        Returns a dict expressing the flow match.
        """
        body = {"oxm_fields": [ofproto.oxm_to_jsondict(k, uv) for k, uv
                               in self._fields],
                "length": self.length
                }
        return {self.__class__.__name__: body}
