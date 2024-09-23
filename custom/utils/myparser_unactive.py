from ryu.ofproto import ofproto_v1_5 as ofproto
from ryu.ofproto.ofproto_v1_5_parser import OFPGroupProp
from ryu.lib.pack_utils import msg_pack_into
import struct

OFPGPT_SELECT_METHOD = 0
OFP_GROUP_PROP_SELECTION_METHOD_PACK_STR = '!HH'
OFP_GROUP_PROP_SELECTION_METHOD_SIZE = 4  # 兩個短整型的大小
# (prop.type, prop.length)

OFPGPT_SELECT_PARAM = 1
OFP_GROUP_PROP_SELECTION_PARAM_PACK_STR = '!HHI'
OFP_GROUP_PROP_SELECTION_PARAM_SIZE = 8  # 兩個短整型 + 一個整型
# (prop.type, prop.length, prop.param)

OFPGPT_SELECT_FIELDS = 2
OFP_GROUP_PROP_SELECTION_FIELD_PACK_STR = '!HHI'
OFP_GROUP_PROP_SELECTION_FIELD_SIZE = 8  # 兩個短整型 + 一個整型
# (prop.type, prop.length, prop.fields_len)

@OFPGroupProp.register_type(OFPGPT_SELECT_METHOD)
class OFPGroupPropSelectionMethod(OFPGroupProp):
    def __init__(self, type_=None, length=None, method=None):
        super(OFPGroupPropSelectionMethod, self).__init__(type_, length)
        self.method = method

    @classmethod
    def parser(cls, buf):
        offset=0
        prop = cls()
        (prop.type, prop.length) = struct.unpack_from(
            OFP_GROUP_PROP_SELECTION_METHOD_PACK_STR, buf, offset)
        offset += OFP_GROUP_PROP_SELECTION_METHOD_SIZE  # 移動到method資料起始點
        method_len = prop.length - OFP_GROUP_PROP_SELECTION_METHOD_SIZE
        
        prop.method = buf[offset:offset+method_len].decode('ascii')
        return prop

    def serialize(self):
        buf = bytearray()

        method_encoded = self.method.encode('ascii')
        self.length = OFP_GROUP_PROP_SELECTION_METHOD_SIZE + len(method_encoded)

        # 填充，使 length 为 8 的倍数
        padding = (8 - (self.length % 8)) % 8  # 計算填充的字節數

        msg_pack_into(OFP_GROUP_PROP_SELECTION_METHOD_PACK_STR, buf, 0, self.type, self.length)
        buf.extend(method_encoded)

        # 在 buf 中追加填充字节
        if padding > 0:
            buf.extend(bytearray(padding))

        return buf

@OFPGroupProp.register_type(OFPGPT_SELECT_PARAM)
class OFPGroupPropSelectionParam(OFPGroupProp):
    def __init__(self, type_=None, length=None, param=0):
        super(OFPGroupPropSelectionParam, self).__init__(type_, length)
        self.param = param

    @classmethod
    def parser(cls, buf):
        prop = cls()
        (prop.type, prop.length, prop.param) = struct.unpack_from(OFP_GROUP_PROP_SELECTION_PARAM_PACK_STR, buf, 0)
        
        return prop

    def serialize(self):
        buf = bytearray()
        self.length = OFP_GROUP_PROP_SELECTION_PARAM_SIZE
        msg_pack_into(OFP_GROUP_PROP_SELECTION_PARAM_PACK_STR, buf, 0, self.type, self.length, self.param)
        return buf

@OFPGroupProp.register_type(OFPGPT_SELECT_FIELDS)
class OFPGroupPropSelectionField(OFPGroupProp):
    def __init__(self, type_=None, length=None, fields=None):
        super(OFPGroupPropSelectionField, self).__init__(type_, length)
        self.fields = fields if fields else []

    @classmethod
    def parser(cls, buf):
        offset = 0
        prop = cls()
        (prop.type, prop.length, fields_len) = struct.unpack_from(OFP_GROUP_PROP_SELECTION_FIELD_PACK_STR, buf, offset)
        offset += OFP_GROUP_PROP_SELECTION_FIELD_SIZE
        prop.fields = [struct.unpack_from('!I', buf, offset + i * 4)[0] for i in range(fields_len)]
        return prop

    def serialize(self):
        buf = bytearray()
        self.length = OFP_GROUP_PROP_SELECTION_FIELD_SIZE + len(self.fields) * 4
        padding = (8 - (self.length % 8)) % 8  # 計算填充的字節數
        
        msg_pack_into(OFP_GROUP_PROP_SELECTION_FIELD_PACK_STR, buf, 0, self.type, self.length, len(self.fields))
        for field in self.fields:
            msg_pack_into('!I', buf, len(buf), field)
        
        buf += b'\x00' * padding  # 添加填充字節
        return buf

