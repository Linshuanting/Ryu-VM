import json
import re

class ssh_parser():
    def __init__(self):
        pass

    def ssh_data_serializer(self, 
                            hostname, 
                            ip = None, 
                            username = None,
                            password = None,
                            key_file = None):
        data = {
            "hostname": hostname,
            "ip": ip,
            "username": username,
            "password": password,
            "key_file": key_file
        }
        return {k: v for k, v in data.items() if v is not None}

    def send_packet_serializer(self,
                               hostname,
                               src_ip=None, 
                               dst_ip=None,
                               fl_number_start=None,
                               port = None):
        data = {
            "hostname": hostname,
            "src": src_ip,
            "dst": dst_ip,
            "flabel": fl_number_start,
            "port": port
        }
        return {k: v for k, v in data.items() if v is not None}

        