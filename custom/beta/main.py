import json
import re
import subprocess, random
from typing import Dict, Tuple, List, Set
from algorithm.greedy import myAlgorithm  # 替换为你的主代码文件名
from data_structure.topo_data_structure import Topology
from custom.beta.PyQt_GUI.rest_client import RestAPIClient
from tools.topo_parser import TopologyParser
from custom.beta.deprecated.mininet_connect import MininetSSHManager
from tools.utils import print_json, to_dict

def start_controller():
    ryu_command = ["ryu-manager", "custom/topo_learn.py"]  # 替换为你的 Ryu 应用路径

    try:
        # 启动 Ryu 控制器
        process = subprocess.Popen(ryu_command)
        print(f"Ryu controller started with PID: {process.pid}")
        # 返回进程对象以便后续控制
        return process
    except Exception as e:
        print(f"Failed to start Ryu controller: {e}")
        return None
    
def run_algorithm(nodes, links, caps, coms) -> Dict[str, Dict[Tuple[str, str], float]]:
    
    # Nodes, Links, Capacities, Commodities
    algorithm = myAlgorithm(nodes, links, caps, coms)
    res = algorithm.run(3, 3)
    print("------- result --------")
    algorithm.print_result(res)

    return res

def get_bandwidth(links):
    
    capacities = {}

    for a, b in links:
        capacity = 0
        if a.startswith("h") or b.startswith("h"):
            capacity = 50
        elif a.startswith("s999") or b.startswith("s999"):
            capacity = 0
        else:
            capacity = 20
        capacities[f"{a}-{b}"] = capacities.get(f"{a}-{b}", capacity)
    return capacities

def get_commodity(nodes, num):

    commodities = []
    h_nodes = [n for n in nodes if n.startswith('h')]
    if 'hffff' in h_nodes:
        h_nodes.remove('hffff')

    for i in range(num):
        
        commodity_name = f"commodity{i+1}"

        if not h_nodes:
            break

        src = random.choice(h_nodes)
        possible_dsts = [node for node in h_nodes if node != src]
        dst_cnt = random.randint(1, 3)
        chosen_dst = random.sample(possible_dsts, min(dst_cnt, len(possible_dsts)))

        demand_val = random.randint(5, 30)

        commodity_data = {
            "name": commodity_name,
            "source": src,
            "destinations": chosen_dst,
            "demand": demand_val
        }

        commodities.append(commodity_data)
    
    return commodities

def print_commodities(commodities):

    print("----- commodities -------")

    for data in commodities:
        print(json.dumps(data, indent=2))

def connect_to_host_and_send_cmd(mininet:MininetSSHManager, commodities:dict):

    for data in commodities:
        src = data['source']
        dsts = data['destinations']
        
        mininet.run_source_cmd(src)
        mininet.run_destinations_cmd(dsts)

url = "http://127.0.0.1:8080"

if __name__ == "__main__":
    print("Program started...")

    client = RestAPIClient(url)
    data_from_controller = client.fetch_json_data()
    
    parser = TopologyParser(data_from_controller)
    parser.run()

    print("--- start print data ---")
    parser.print_parse_data()

    nodes = parser.get_nodes()
    links = parser.get_links()
    capacities = get_bandwidth(links)
    commodities = get_commodity(nodes, 2)

    # mininet = MininetSSHManager(parser.get_single_ip_from_all_hosts())
    # connect_to_host_and_send_cmd(mininet, commodities)

    print(nodes)
    print(links)
    print(capacities)
    print_commodities(commodities)

    res = run_algorithm(nodes, links, capacities, commodities)
    packet = {
        'commodities_and_paths': to_dict(res),
        'commodities_data': commodities
    }
    print(type(packet))
    print(packet)
    print(client.post_json_data(packet))


    


