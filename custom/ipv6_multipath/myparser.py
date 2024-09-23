from ryu.ofproto import ofproto_v1_5 as ofproto
from ryu.ofproto.ofproto_v1_5_parser import OFPGroupProp
import struct

@OFPGroupProp.register_type(ofproto.OFPGPT_EXPERIMENTER) 
class OFPGroupPropSelectionMethod(OFPGroupProp):
    def __init__(self, method, param=0, fields=None):
        super(OFPGroupPropSelectionMethod, self).__init__(ofproto.OFPGPT_EXPERIMENTER)
        self.method = method
        self.param = int(param)  # 确保 param 是整数类型
        self.fields = fields if fields else []
        self.len = None  # 初始化长度属性

    @classmethod
    def parser(cls, buf, offset):
        msg = cls()
        msg.len, method_len = struct.unpack_from('!HH', buf, offset)
        offset += 4
        msg.method = buf[offset:offset + method_len].decode('ascii')
        offset += method_len
        fields_len = struct.unpack_from('!H', buf, offset)[0]
        offset += 2
        msg.fields = []
        for _ in range(fields_len):
            field = struct.unpack_from('!I', buf, offset)[0]
            msg.fields.append(field)
            offset += 4
        return msg

    def serialize(self, buf, offset):
        method_encoded = self.method.encode('ascii')
        self.len = 4 + len(method_encoded) + 2 + len(self.fields) * 4

        if len(buf) < offset + self.len:
            buf.extend(bytearray(offset + self.len - len(buf)))

        # 确保所有打包数据都是整数
        struct.pack_into('!HH', buf, offset, self.len, len(method_encoded))
        offset += 4
        buf[offset:offset + len(method_encoded)] = method_encoded
        offset += len(method_encoded)
        struct.pack_into('!H', buf, offset, len(self.fields))
        offset += 2
        for field in self.fields:
            if not isinstance(field, int):
                raise ValueError(f"Field {field} is not an integer.")
            struct.pack_into('!I', buf, offset, field)
            offset += 4