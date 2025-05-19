from typing import List, Dict, Tuple, Set
import re, json, random
import time
import csv
import os
from new_mcfp_model import MultiCommodityFlowProblem
from greedy import myAlgorithm

current_dir = os.path.dirname(os.path.abspath(__file__))

def get_mcfp_topo_data(topo, trees=5)->List:
    nodes = [node["name"] for node in topo["nodes"]]
    
    links = []
    for link in topo["links"]:
        n1, n2 = link["link"].split("-")
        links.append((n1, n2))
        links.append((n2, n1))

    capacities = {}
    for info in topo['links']:
        node1, node2 = info["link"].split('-')
        capacities[(node1, node2)] = info["bw"]  
        capacities[(node2, node1)] = info["bw"]

    mcfp_input = [nodes, links, capacities, trees]

    return mcfp_input

def get_myalgorithm_topo_data(topo)->List:
    nodes = [node["name"] for node in topo["nodes"]]
    links = {}
    for info in topo["links"]:
        bw = info["bw"]
        n1, n2 = info["link"].split('-')
        links[f"{n1}-{n2}"] = bw
        links[f"{n2}-{n1}"] = bw
    
    return [nodes, links]

def generate_random_commodity(amount, demand_min, demand_max, nodes):
    myalg_commodities = []
    mcfp_commodities = []
    h_nodes = [n for n in nodes if n.startswith('h')]
    if 'hffff' in h_nodes:
        h_nodes.remove('hffff')

    for i in range(1, 1+amount):
        
        commodity_name = f"commodity{i}"

        if not h_nodes:
            break

        src = random.choice(h_nodes)
        possible_dsts = [node for node in h_nodes if node != src]
        dst_cnt = random.randint(1, 3)
        chosen_dst = random.sample(possible_dsts, min(dst_cnt, len(possible_dsts)))

        demand_val = random.randint(demand_min, demand_max)

        commodity_data = {
            "name": commodity_name,
            "source": src,
            "destinations": chosen_dst,
            "demand": demand_val
        }

        myalg_commodities.append(commodity_data)

        mcfp_commodities.append((src, chosen_dst, demand_val))
    
    return mcfp_commodities, myalg_commodities

def generate_average_dst_commodity(amount, demand_min, demand_max, nodes):
    myalg_commodities = []
    mcfp_commodities = []
    avoid_duplicated_dsts = []

    h_nodes = [n for n in nodes if n.startswith('h')]
    if 'hffff' in h_nodes:
        h_nodes.remove('hffff')

    for i in range(1, 1+amount):
        commodity_name = f"commodity{i}"

        if not h_nodes:
            break

        src = random.choice(h_nodes)
        possible_dsts = [node for node in h_nodes if node != src and node not in avoid_duplicated_dsts]

        dst_cnt = random.randint(1, 3)
        
        if len(possible_dsts) < 3:
            avoid_duplicated_dsts = []
        
        chosen_dst = random.sample(possible_dsts, min(dst_cnt, len(possible_dsts)))
        demand_val = random.randint(demand_min, demand_max)
        avoid_duplicated_dsts.extend(chosen_dst)

        commodity_data = {
            "name": commodity_name,
            "source": src,
            "destinations": chosen_dst,
            "demand": demand_val
        }
        myalg_commodities.append(commodity_data)
        mcfp_commodities.append((src, chosen_dst, demand_val))
    
    return mcfp_commodities, myalg_commodities

def print_commodities(commodities):
    for commodity in commodities:
        print(f"name: {commodity['name']}")
        print(f"   source: {commodity['source']}")
        print(f"   destinations: {commodity['destinations']}")
        print(f"   demand: {commodity['demand']}")
        print("--------------------------")

def run_mcfp_solver(data, commodities):
    nodes = data[0]
    links = data[1]
    capacities = data[2]
    trees = data[3]
    mcfp_solver = MultiCommodityFlowProblem(
        nodes, links, commodities, capacities, trees
    )
    mcfp_solver.add_constraints()
    mcfp_solver.solve()

    # mcfp_solver.get_solve()
    mcfp_solver.finish_solver()
    res = mcfp_solver.get_total_throughput()

    print(f"mcfp res: {res}")
    return res

def run_myalgorithm(data, commodities):
    nodes = data[0]
    links = data[1]

    myalg = myAlgorithm(
        nodes, links, commodities
    )
    res = myalg.run(3, 3)
    # myalg.print_result(res)

    res = myalg.get_throughput(res)

    print(f"myalgorithm res: {res}")
    return res

def compare_result(mcfp_res, myalg_res):
    data_len = len(mcfp_res)
    
    def sum_list(arr):
        res = 0
        for a in arr:
            res += a
        return res

    compare_res = []
    for i in range(data_len):
        sum1 = mcfp_res[i]
        sum2 = sum_list(myalg_res[i])
        compare_res.append(sum2/sum1)
    
    return compare_res

if __name__ == "__main__":
    with open('/home/user/mininet/custom/topology.json', 'r') as file:
        data = json.load(file)
    
    topology_name = "spine_leaf_topology"
    topo = data['topologies'][topology_name]
    csv_file = f"{current_dir}/graph/runtime_comparison.csv"

    mcfp_data = get_mcfp_topo_data(topo, 5)
    myalg_data = get_myalgorithm_topo_data(topo)

    mcfp_times = []
    myalg_times = []
    mcfp_throughputs = []
    myalg_throughputs = []
    compare_ratios = []

    count = 100

    for i in range(count):

        print(f"----- Round {i+1} -----------------")

        # mcfp_commodities, myalg_commodities = generate_random_commodity(
        #     6, 10, 20, [node["name"] for node in topo["nodes"]]
        # )
        mcfp_commodities, myalg_commodities = generate_average_dst_commodity(
            4, 10, 20, [node["name"] for node in topo["nodes"]]
        )

        print_commodities(myalg_commodities)

        # Run mcfp
        start_time = time.time()
        mcfp_res = run_mcfp_solver(mcfp_data, mcfp_commodities)
        mcfp_time = time.time() - start_time
        mcfp_times.append(mcfp_time)
        mcfp_total = sum(mcfp_res)
        mcfp_throughputs.append(mcfp_total)

        # Run my algorithm
        start_time = time.time()
        myalg_res = run_myalgorithm(myalg_data, myalg_commodities)
        myalg_time = time.time() - start_time
        myalg_times.append(myalg_time)
        myalg_total = sum(sum(sublist) for sublist in myalg_res)
        myalg_throughputs.append(myalg_total)

        # 比例
        compare_ratio = myalg_total / mcfp_total if mcfp_total != 0 else 0
        compare_ratios.append(compare_ratio)

        # time.sleep(0.5)

    # 平均
    avg_mcfp_time = sum(mcfp_times) / len(mcfp_times)
    avg_myalg_time = sum(myalg_times) / len(myalg_times)
    avg_mcfp_throughput = sum(mcfp_throughputs) / len(mcfp_throughputs)
    avg_myalg_throughput = sum(myalg_throughputs) / len(myalg_throughputs)
    avg_compare_ratio = sum(compare_ratios) / len(compare_ratios)

    print("\n=== Average Results ===")
    print(f"MCFP - Avg Time: {avg_mcfp_time:.4f}s, Avg Throughput: {avg_mcfp_throughput:.4f}")
    print(f"MyAlg - Avg Time: {avg_myalg_time:.4f}s, Avg Throughput: {avg_myalg_throughput:.4f}")
    print(f"Compare Ratio (MyAlg / MCFP) Avg: {avg_compare_ratio:.4f}")

    # 寫入 CSV
    with open(csv_file, "w", newline="") as csvfile:
        fieldnames = ["run", "mcfp_time", "myalg_time", "mcfp_throughput", "myalg_throughput", "compare_ratio"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for i in range(count):
            writer.writerow({
                "run": i + 1,
                "mcfp_time": f"{mcfp_times[i]:.6f}",
                "myalg_time": f"{myalg_times[i]:.6f}",
                "mcfp_throughput": f"{mcfp_throughputs[i]:.2f}",
                "myalg_throughput": f"{myalg_throughputs[i]:.2f}",
                "compare_ratio": f"{compare_ratios[i]:.4f}"
            })

    


