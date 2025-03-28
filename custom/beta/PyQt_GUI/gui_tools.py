import json
import re
import subprocess, random
from typing import Dict, Tuple, List, Set
from custom.beta.algorithm.greedy import myAlgorithm

def get_bandwidth(links):
    
    capacities = {}

    for link in links.keys():
        a, b = link.rsplit("-", 1)  # 源设备
        capacity = 0
        if a.startswith("h") or b.startswith("h"):
            capacity = 50
        else:
            capacity = 20
        capacities[f"{a}-{b}"] = capacities.get(f"{a}-{b}", capacity)
    return capacities

def get_commodity(nodes, num, start=1):

    commodities = []
    h_nodes = [n for n in nodes if n.startswith('h')]
    if 'hffff' in h_nodes:
        h_nodes.remove('hffff')

    for i in range(start, start + num):
        
        commodity_name = f"commodity{i}"

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

def run_algorithm(nodes, links, coms) -> Dict[str, Dict[Tuple[str, str], float]]:
    
    # Nodes, Links, Capacities, Commodities
    algorithm = myAlgorithm(nodes, links, coms)
    res = algorithm.run(3, 3)

    return res