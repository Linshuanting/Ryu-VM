from collections import defaultdict as ddict
from sortedcontainers import SortedList
from typing import List, Dict, Tuple, Set
import re
import logging
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from beta.tools.utils import tuple_to_str, to_dict, str_to_tuple

logging.basicConfig(
    level=logging.INFO, # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    # datefmt="%Y-%m-%d %H:%M:%S,"
    filename="topology.log",
    filemode="w" # 覆蓋， "a" 表示附加到檔案尾端
)
logger = logging.getLogger(__name__)

class Topology():

    MULTI_GROUP_IP_STARTWITH = 'ff38'
    SINGLE_IP_STARTWITH = '2001'

    def __init__(self):
        self.reset()

    def reset(self):
        """ 重置所有成員變數，使其回到初始狀態 """
        logger.info("Resetting Topology Data...")

        # (u, v) link to (p, q) port using on switch u, v, respectively
        self.links = {}
        # (u, v) link to its max_speed bandwidth
        self.link_bw = {}
        # host_name to host_context
        self.hosts = {}
        # host_mac_addr to host_name
        self.mac_to_host = {}
        # host_ip to host_name
        self.ip_to_host = {}
        # dp_id -> datapath
        self.datapath = {}
        # sw_mac to sw_id, sw_port
        self.sw_mac_to_sw_context = {}
        
        self.host_counter = 0

        logger.info("Topology reset complete.")

    def set_link(self, u, v, port_u, port_v):
        u, v = self.turn_to_key(u), self.turn_to_key(v)
        if (u, v) in self.links:
            logger.debug(f"Set the same Link: {u}-{v}")
            return 
        self.links[(u, v)] = (port_u, port_v)
    
    def get_link(self, u, v) -> Tuple[int, int]:
        u, v = self.turn_to_key(u), self.turn_to_key(v)
        return self.links[(u, v)]
    
    def get_links(self) -> Dict:
        return self.links

    def del_link(self, u, v=None):
        """刪除 self.links 中的鏈路 (u, v) 或 (u, *)"""
        if self.get_hostName_from_mac(u) is None:
            return
        u = self.turn_to_key(u)  # 轉換 key
        if v is not None:
            v = self.turn_to_key(v)  # 轉換 key
            # 刪除指定 (u, v) 鏈路
            if (u, v) in self.links:
                del self.links[(u, v)]
                logger.info(f"刪除鏈路: ({u}, {v})")
            if (v, u) in self.links:  # 確保雙向刪除
                del self.links[(v, u)]
                logger.info(f"刪除鏈路: ({v}, {u})")
        else:
            # 刪除所有與 u 相關的鏈路
            keys_to_delete = [key for key in self.links if u in key]
            for key in keys_to_delete:
                del self.links[key]
                logger.info(f"刪除鏈路: {key}")
    
    def set_link_bandwidth(self, u, v, bw):
        u, v = self.turn_to_key(u), self.turn_to_key(v)
        if (u, v) in self.link_bw and self.link_bw[(u, v)] is not None:
            return 
        self.link_bw[(u, v)] = bw

    def get_link_bandwidth(self, u, v):
        if (u, v) in self.link_bw:
            return self.link_bw[(u, v)]
        return None
    
    def del_link_bandwidth(self, u, v):
        if self.get_hostName_from_mac(u) is None:
            return
        u = self.turn_to_key(u)  # 轉換 key
        if v is not None:
            v = self.turn_to_key(v)  # 轉換 key
            # 刪除指定 (u, v) 鏈路
            if (u, v) in self.link_bw:
                del self.link_bw[(u, v)]
                logger.info(f"刪除鏈路: ({u}, {v})")
            if (v, u) in self.link_bw:  # 確保雙向刪除
                del self.link_bw[(v, u)]
                logger.info(f"刪除鏈路: ({v}, {u})")
        else:
            # 刪除所有與 u 相關的鏈路
            keys_to_delete = [key for key in self.link_bw if u in key]
            for key in keys_to_delete:
                del self.link_bw[key]
                logger.info(f"刪除鏈路: {key}")
    
    def print_links(self):
        print("------ Current Links ------")
        for (u, v), (port_u, port_v) in self.links.items():
            print(f"Link: {u} -> {v}, Ports: {port_u} -> {port_v}")

    def set_host(self, host_mac, host_ip, sw_id, sw_in_port):
        name = self.set_hostName_from_mac(host_mac)
        
        if host_ip not in self.ip_to_host:
            self.ip_to_host[host_ip] = [name]
        elif name not in self.ip_to_host[host_ip]:  # 直接檢查，不用 pass
            self.ip_to_host[host_ip].append(name)

        if name in self.hosts:
            if host_ip not in self.hosts[name]['IPs']:
                self.hosts[name]['IPs'].add(host_ip)
                return 
            logger.warning(f"Set the same Host:{name}, HostIP:{host_ip}, Mac:{host_mac}")
            return
        data = {
            'mac': host_mac,
            'IPs': SortedList([host_ip]),
            'sw_id': sw_id,
            'sw_in_port': sw_in_port
        }
        self.hosts[name] = data
        return
    
    def del_host(self, host_mac = None, host_name = None):
        logger.info(f'Del host: {host_mac}, hostName:{self.get_hostName_from_mac(host_mac)}')
        if host_mac:
            name = self.get_hostName_from_mac(host_mac)
        if host_name:
            name = host_name
        
        if name in self.hosts:
            # 移除該 host 相關的 IP
            for ip in self.hosts[name]["IPs"]:
                if ip in self.ip_to_host:
                    self.ip_to_host[ip].remove(name)  # 從列表中刪除 Host
                    if not self.ip_to_host[ip]:  # 如果列表空了，刪除 IP
                        del self.ip_to_host[ip]
                        
            # 刪除 host 記錄
            del self.hosts[name]
            self.del_hostName(host_mac)
    
    def get_connecting_host_switch_data(self, host_name=None, host_mac=None) -> Tuple[int, int]:
        if host_name is not None and host_name in self.hosts:
            return self.hosts[host_name]['sw_id'], self.hosts[host_name]['sw_in_port']
        elif host_mac is not None and self.get_hostName_from_mac(host_mac) in self.hosts:
            name = self.get_hostName_from_mac(host_mac)
            return self.hosts[name]['sw_id'], self.hosts[name]['sw_in_port']
    
    def get_host_IP(self, host_name=None, host_mac=None) -> List:
        if host_name is not None and host_name in self.hosts:
            return self.hosts[host_name]['IPs']
        elif host_mac is not None and self.get_hostName_from_mac(host_mac) in self.hosts:
            return self.hosts[self.get_hostName_from_mac(host_mac)]['IPs']

    def get_host_single_ipv6(self, host) -> str:
        # 取得 host，若是使用 host 的 mac 當輸入也可辨別
        if self.is_mac(host):
            host = self.get_hostName_from_mac(host)
        
        for ip in self.hosts[host]['IPs']:
            if ip.startswith(self.SINGLE_IP_STARTWITH):
                return ip
        
        logger.warning(f"the host:{host}, not have single ipv6 startswith {self.SINGLE_IP_STARTWITH}")
        return None
    
    def get_hostName_from_ip(self, ip):
        if ip in self.ip_to_host:
            return self.ip_to_host[ip]
        else:
            return None
    
    def get_all_host_single_ipv6(self) -> dict:
        
        hosts = {}
        for host, data in self.hosts.items():
            ip = self.get_host_single_ipv6(host)
            if ip is not None:
                hosts[host] = ip
        
        return hosts
        
    def get_host_multi_group_IP(self, host_name=None, host_mac=None) -> str:
        
        if host_name is not None:
            name = host_name
        elif host_mac is not None:
            name = self.get_hostName_from_mac(host_mac)
            if name is None:
                logger.warning(f"the mac:{host_mac} doesn't exist in hosts database")
                return None
        else:
            logger.warning(f"the invalid input")
            return None
        
        if name not in self.hosts:
            logger.warning(f"the name:{name} doesn't exist in database")

        for ip in self.hosts[name]['IPs']:
            if ip.startswith(self.MULTI_GROUP_IP_STARTWITH):
                return ip
        
        logger.warning(f"the host:{name}, not have multi group ip")
        return 

    def get_host_mac(self, host_name=None, host_ip=None) -> str:
        # 檢查 host_name 是否有效
        if host_name:
            if host_name in self.hosts:
                return self.hosts[host_name]['mac']
            logger.warning(f"Host name '{host_name}' does not exist.")

        # 檢查 host_ip 是否有效
        if host_ip:
            for host_info in self.hosts.values():
                if 'IPs' in host_info and host_ip in host_info['IPs']:
                    return host_info['mac']
            logger.warning(f"Host IP '{host_ip}' does not exist in any host.")

        # 如果未提供任何有效參數
        logger.warning("Both host_name and host_ip are None or invalid.")
        return None

    def get_hostName_from_mac(self, mac) -> str:
        if mac in self.mac_to_host:
            return self.mac_to_host[mac]
        logger.warning(f"Not have the host mac:{mac} in mac_to_host database")
        return None
    
    def set_hostName_from_mac(self, mac) -> str:
        if mac in self.mac_to_host:
            logger.debug(f"Already set the mac:{mac} in hostName database")
            return self.mac_to_host[mac]
        
        # self.mac_to_host[mac] = f"h{self.host_counter}"
        self.host_counter+=1

        # 提取 MAC 地址的最後兩個字節
        last_two_bytes = mac.split(":")[-2:]  # 取最後兩個
        host_suffix = "".join(last_two_bytes).lstrip("0")  # 移除前導 0
        self.mac_to_host[mac] = f"h{host_suffix}"

        return self.mac_to_host[mac]
    
    def del_hostName(self, mac):
        if mac in self.mac_to_host:
            del self.mac_to_host[mac]
        else:
            logger.debug(f'the hostName and host is not exist, can not delete')
    
    def contain_IP(self, IP = None) -> bool:
        for name, host_info in self.hosts.items():
            for host_ip in host_info['IPs']:
                if host_ip == IP:
                    return True
        return False 
    
    def contain_host(self, name=None, mac=None) -> bool:
        if mac and mac in self.mac_to_host:  # 如果 mac 有值且存在於 mac_to_host
            return True
        if name and name in self.hosts:  # 如果 name 有值且存在於 hosts
            return True
        return False

    def print_hosts(self):
        print("------ Get all hosts ------")
        for mac, info in self.hosts.items():
            print(f"host mac: {mac}, "
                  f"host ips: {info['IPs']}, "
                  f"switch id: {info['sw_id']}, "
                  f"switch port: {info['sw_in_port']}")
    
    # return switch id
    def set_datapath(self, datapath, id=None) -> int:
        if id is None:
            id = datapath.id
        id = self.turn_to_key(id)
        if id not in self.datapath:
            self.datapath[id] = datapath
        else:
            tmp = self.datapath[id]
            self.datapath[id] = datapath
            logger.debug(f"the sw_id:{id} is exist, new datapath:{datapath} overwrites the old datapath:{tmp}")
        return id
    
    def del_datapath(self, datapath, id=None):
        """ 刪除指定的 Datapath """
        if id is None:
            id = datapath.id  # 如果未提供 id，則使用 datapath.id
        id = self.turn_to_key(id)  # 轉換 id 以確保一致性

        if id in self.datapath:
            del self.datapath[id]  # 從字典中刪除該 Datapath
            self.del_link(datapath)

            logger.info(f"刪除交換機 {id} (datapath: {datapath})")
        else:
            logger.warning(f"交換機 {id} 不存在，無法刪除")
    
    def get_datapath(self, id):
        id = self.turn_to_key(id)
        if id in self.datapath:
            return self.datapath[id]
        logger.warning(f"the sw_id:{id} is not exist")
        return None
    
    def get_datapaths(self) -> Dict:
        return self.datapath
    
    def print_datapath(self):
        print(f'------ Datapath ------')
        for id, dp in self.datapath.items():
            print(f"id: {id}, datapath: {dp}")

    def set_sw_mac_to_context(self, mac, sw_id, sw_port):
        if mac in self.sw_mac_to_sw_context:
            logger.debug(f"the sw_id:{sw_id}, already saved the mac addr {mac}")
            return 
        self.sw_mac_to_sw_context[mac] = (sw_id, sw_port)

    def contain_sw_mac(self, mac) -> bool:
        if mac in self.sw_mac_to_sw_context:
            return True
        return False

    def is_mac(self, s):
        if isinstance(s, str) is False:
            return False
        return bool(re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", s)) 
    
    def is_host(self, name=None, mac=None):
        if name and name in self.hosts:
            return True
        if mac:
            for info in self.hosts.values():
                if mac == info['mac']:
                    return True
        return False

    def turn_to_key(self, obj):
        if isinstance(obj, int):
            return str(obj)
        elif self.is_mac(obj):
            return self.mac_to_host[obj]
        return obj
    
    def data_to_dict(self):
        return{
            "links": to_dict(self.links),
            "hosts": to_dict(self.hosts),
            "links_bw": to_dict(self.link_bw)
        }