from collections import defaultdict as ddict
from sortedcontainers import SortedList
from typing import List, Dict, Tuple, Set
import re
import logging
from utils import tuple_to_str, to_dict, str_to_tuple

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

    def __init__(self):
        
        # (u, v) link to (p, q) port using on switch u, v, respectively
        self.links = {}
        # host_name to host_context
        self.hosts = {}
        # host_mac_addr to host_name
        self.mac_to_host = {}
        # dp_id -> datapath
        self.datapath = {}
        # sw_mac to sw_id, sw_port
        self.sw_mac_to_sw_context = {}
        # the commodity to paths, calculating by algorithm
        # commodity: {node1: [each of nodes the node1 connects]}
        # commodity: {(u, v): bandwidth}
        self.commodities_to_paths = {}
        # save all commodity
        self.commodities = []
        self.host_counter = 0

        self.test_datapath = None
        self.test_dpid = None
    
    def set_test_dp(self, datapath, dpid):
        self.test_datapath = datapath
        self.test_dpid = dpid
    def get_test_dp(self):
        return self.test_datapath
    def get_test_dpid(self):
        return self.test_dpid

    def set_link(self, u, v, port_u, port_v):
        u, v = self.turn_to_key(u), self.turn_to_key(v)
        if (u, v) in self.links:
            logger.debug(f"Set the same Link: {u}-{v}")
            return 
        self.links[(u, v)] = (port_u, port_v)
    
    def get_link(self, u, v) -> Tuple[int, int]:
        u, v = self.turn_to_key(u), self.turn_to_key(v)
        return self.links[(u, v)]
    
    def print_links(self):
        print("------ Current Links ------")
        for (u, v), (port_u, port_v) in self.links.items():
            print(f"Link: {u} -> {v}, Ports: {port_u} -> {port_v}")

    def set_host(self, host_mac, host_ip, sw_id, sw_in_port):
        name = self.set_hostName_from_mac(host_mac)
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
        
        self.mac_to_host[mac] = f"h{self.host_counter}"
        self.host_counter+=1

        return self.mac_to_host[mac]
    
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
    
    def get_datapath(self, id):
        id = self.turn_to_key(id)
        if id in self.datapath:
            return self.datapath[id]
        logger.warning(f"the sw_id:{id} is not exist")
    
    def print_datapath(self):
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

    # def set_commodities_and_paths(self, data):
    #     for commodity, links_context in data.items():
    #         self.commodities_to_paths[commodity] = self.set_paths(links_context)

    # def set_paths(self, links):
    #     commodity = {}
    #     print(f"links in set paths: {links}")
    #     for link, bandwidth in links.items():
    #         u, v = str_to_tuple(link)
    #         if u not in commodity:
    #             commodity[u] = [(v, bandwidth)]
    #         else:
    #             commodity[u].append((v, bandwidth))
    #     return commodity
    
    # def get_paths(self, commodity) -> Dict[str, List]:
    #     return self.commodities_to_paths[commodity]
    
    # def get_commodities_and_paths(self) -> Dict[str, Dict[str, List]]:
    #     return self.commodities_to_paths

    # def clear_all_commodities(self):
    #     self.commodities_to_paths.clear()
    
    # def print_commodities_and_paths(self):
    #     print("------ Commodities and Their Paths ------")
    #     for commodity, paths in self.commodities_to_paths.items():
    #         print(f"Commodity: {commodity}")
    #         for u, v_list in paths.items():
    #             v_str = ", ".join(v_list)  # 格式化相鄰節點為字符串
    #             print(f"  Node {u} -> [{v_str}]")

    def set_commodities_and_paths(self, data):
        for commodity, context in data.items():
            paths = {}
            for link, bw in context.items():
                u, v = str_to_tuple(link)
                paths[(u, v)] = bw
            self.commodities_to_paths[commodity] = paths
            self.commodities.append(commodity)

    def get_paths(self, commodity):
        if commodity in self.commodities_to_paths:
            return self.commodities_to_paths[commodity]
        logger.warning(f"The commodity:{commodity} is not exist")

    def get_commodities(self):
        return self.commodities

    def is_mac(self, s):
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
            "hosts": to_dict(self.hosts)
        }