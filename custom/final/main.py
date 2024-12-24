import json
import re
import subprocess, random
from typing import Dict, Tuple, List, Set
from algorithm.greedy import myAlgorithm  # 替换为你的主代码文件名
from topo_data import Topology
from rest_client import RestAPIClient
from topo_parser import TopologyParser
from utils import print_json

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
    
def run_algorithm(nodes, links, caps, coms):
    
    # Nodes, Links, Capacities, Commodities
    algorithm = myAlgorithm(nodes, links, caps, coms)
    res = algorithm.run(3, 3)
    print("------- result --------")
    algorithm.print_result(res)


def get_bandwidth(links):
    
    capacities = {}

    for a, b in links:
        capacity = 0
        if a.startswith("h") or b.startswith("h"):
            capacity = 50
        else:
            capacity = 20
        capacities[f"{a}-{b}"] = capacities.get(f"{a}-{b}", capacity)
    return capacities

def get_commodity(nodes, num):

    commodities = []
    h_nodes = [n for n in nodes if n.startswith('h')]

    for i in range(num):
        
        commodity_name = f"commodity{i+1}"

        if not h_nodes:
            break

        src = random.choice(h_nodes)
        possible_dsts = [node for node in h_nodes if node != src]
        dst_cnt = random.randint(1, 3)
        chosen_dst = random.sample(possible_dsts, min(dst_cnt, len(possible_dsts)))

        demand_val = random.randint(5, 20)

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

url = "http://127.0.0.1:8080/topology"

if __name__ == "__main__":
    print("Program started...")

    client = RestAPIClient(url)
    data_from_controller = client.fetch_json_data()
    
    parser = TopologyParser(data_from_controller)
    parser.run()

    # print("--- start print data ---")
    # parser.print_parse_data()

    nodes = parser.get_nodes()
    links = parser.get_links()
    capacities = get_bandwidth(links)
    commodities = get_commodity(nodes, 2)

    print(nodes)
    print(links)
    print(capacities)
    print_commodities(commodities)

    run_algorithm(nodes, links, capacities, commodities)
    


