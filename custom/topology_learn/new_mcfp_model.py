from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value
import json
import re

class MultiCommodityFlowProblem:
    def __init__(self, nodes, links, commodities, capacities, trees):
        """
        Initialize the multi-commodity flow problem.
        :param nodes: List of nodes in the graph.
        :param links: List of tuples representing links (u, v) in the graph.
        :param commodities: List of tuples (source, destination, demand) for each commodity.
        :param capacities: Dictionary with capacities for each link (u, v).
        :param trees: Number of spanning trees.
        """
        self.nodes = nodes
        self.links = links
        self.commodities = commodities
        self.capacities = capacities
        self.trees = trees
        self.problem = LpProblem("MultiCommodityFlowProblem", LpMaximize)
        self.variables = self.create_variables()
        self.solution = {}

    def create_variables(self):
        """Create flow, descendant, and capacity variables."""
        variables = {}

        # Flow variables for each commodity k on each link (u, v) in spanning tree c
        for u, v in self.links:
            for k, _ in enumerate(self.commodities):
                for c in range(self.trees):
                    variables[f"f_{u}_{v}_{k}_{c}"] = LpVariable(f"f_{u}_{v}_{k}_{c}", lowBound=0)
        
        for u, v in self.links:
            for k, _ in enumerate(self.commodities):
                for c in range(self.trees):
                    variables[f"x_{u}_{v}_{k}_{c}"] = LpVariable(f"x_{u}_{v}_{k}_{c}", lowBound=0, cat="Binary")

        # Descendant variables for spanning trees
        for u, v in self.links:
            for k, _ in enumerate(self.commodities):
                for c in range(self.trees):
                    variables[f"D_{u}_{v}_{k}_{c}"] = LpVariable(f"D_{u}_{v}_{k}_{c}", lowBound=0, cat="Integer")

        # Z variables for each commodity
        for k, _ in enumerate(self.commodities):
            variables[f"Z_{k}"] = LpVariable(f"Z_{k}", lowBound=0, upBound=1)

        variables[f"Z"] = LpVariable("Z", lowBound=0, upBound=1)

        return variables

    def add_constraints(self):
        """Add constraints based on the problem requirements."""
        # Source constraint
        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            # 流出總流量至少要有 demand * Z_k 的流量
            self.problem += (
                lpSum(self.variables[f"f_{s_k}_{v}_{k}_{c}"] for v in self.nodes if (s_k, v) in self.links for c in range(self.trees))
                >= d_k * self.variables[f"Z_{k}"]
            ), f"SourceConstraint_total_outflow_{k}"
            # 原點流入流量為零
            self.problem += (
                lpSum(self.variables[f"f_{u}_{s_k}_{k}_{c}"] for u in self.nodes if (u, s_k) in self.links for c in range(self.trees))
                == 0
            ), f"SourceConstraint_total_inflow_{k}"

            for c in range(self.trees):    
                # 原點不會是其他人的子孫
                self.problem += (
                    lpSum(self.variables[f"D_{u}_{s_k}_{k}_{c}"] for u in self.nodes if (u, s_k) in self.links)
                    == 0
                ), f"SourceConstraint_source_isn't_decendants{s_k}_{k}_{c}"
                # 原點的子孫數是 V-1
                self.problem += (
                    lpSum(self.variables[f"D_{s_k}_{u}_{k}_{c}"] for u in self.nodes if (s_k, u) in self.links)
                    == len(self.nodes)-1
                ), f"Source_nodes_decendants_amounts_is_V-1_{s_k}_{k}_{c}"

        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            # Destination constraint
            for t in T_k:
                self.problem += (
                    lpSum(self.variables[f"f_{v}_{t}_{k}_{c}"] for v in self.nodes if (v, t) in self.links for c in range(self.trees))
                    >= d_k * self.variables[f"Z_{k}"]
                ), f"DestinationConstraint_{k}_{t}"

        # Spanning tree constraints
        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            for c in range(self.trees):
                for v in self.nodes:
                    if v != s_k:
                        # 進來的子孫數 = 出去的子孫數 +1 
                        self.problem += (
                            lpSum(self.variables[f"D_{u}_{v}_{k}_{c}"] for u in self.nodes if (u, v) in self.links)
                            - lpSum(self.variables[f"D_{v}_{w}_{k}_{c}"] for w in self.nodes if (v, w) in self.links)
                            == 1
                        ), f"SpanningTree_denendants_conservation_{v}_{k}_{c}"

                        self.problem += (
                            lpSum(self.variables[f"x_{u}_{v}_{k}_{c}"] for u in self.nodes if (u, v) in self.links)
                            == 1
                        )
        
        # x variable to check the edge (u,v) is used in spanning tree c
        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            for c in range (self.trees):
                for u, v in self.links:
                    self.problem += (
                        self.variables[f"D_{u}_{v}_{k}_{c}"] <= len(self.nodes)*self.variables[f"x_{u}_{v}_{k}_{c}"]
                    )
                                        

        # Flow Conservation
        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            for c in range(self.trees):
                for v in self.nodes:
                    if v != s_k and v not in T_k:
                        for w in self.nodes:
                            if (v, w) in self.links:
                                self.problem += (
                                    lpSum(self.variables[f"f_{u}_{v}_{k}_{c}"] for u in self.nodes if (u, v) in self.links)
                                    >= self.variables[f"f_{v}_{w}_{k}_{c}"]
                                ), f"Flow_Conservation_{s_k}_{v}_{w}_{k}_{c}"
        
        # 流量根據 x 決定，x > 0 才會有流量
        for k, (s_k, T_k, d_k) in enumerate(self.commodities):
            for u, v in self.links:
                for c in range(self.trees):
                    self.problem += (
                        self.variables[f"f_{u}_{v}_{k}_{c}"] 
                        <= self.variables[f"x_{u}_{v}_{k}_{c}"] *self.capacities[(u,v)]
                    ), f"Flow_constraint_upperbound_on_{u}_{v}_{k}_{c}"

        # Capacity constraint
        for u, v in self.links:
            self.problem += (
                lpSum(self.variables[f"f_{u}_{v}_{k}_{c}"] for k, _ in enumerate(self.commodities) for c in range(self.trees))
                <= self.capacities[(u, v)]
            ), f"CapacityConstraint_{u}_{v}"

        # Objective function
        # 1. 定義目標函數，最大化 Z
        self.problem += self.variables["Z"], "Objective"

        # 2. 添加約束 Z <= Z_k 對於所有 k
        for k in range(len(self.commodities)):
            self.problem += self.variables["Z"] <= self.variables[f"Z_{k}"], f"Z_constraint_{k}"


    def solve(self):
        """Solve the optimization problem and print the results."""
        self.problem.solve()

        solution = {}
        for v in self.problem.variables():
            solution[v.name] = value(v)
        
        self.solution = solution

    def get_solve(self):
        z_vars = []
        f_vars = []
        d_vars = []

        for name, value in self.solution.items():
            if name.startswith("Z"):
                z_vars.append((name, value))
            if name.startswith("f"):
                f_vars.append((name, value))
            if name.startswith("D"):
                d_vars.append((name, value))
        
        # Sort within each group by the second last and last indices
        f_vars.sort(key=lambda x: (int(x[0].split('_')[-2]), int(x[0].split('_')[-1]))) 
        d_vars.sort(key=lambda x: (int(x[0].split('_')[-2]), int(x[0].split('_')[-1])))

        print("Solution:")

        for name, value in z_vars:
            print(f"{name}: {value}")

        # Print F variables grouped by the second last and last indices
        current_second_last = None
        current_last = None
        for name, value in f_vars:
            second_last = name.split('_')[-2]
            last = name.split('_')[-1]
            if second_last != current_second_last:
                current_second_last = second_last
                current_last = None
                print(f"\nF variables for second last group {current_second_last}:")
            if last != current_last:
                current_last = last
                print(f"  Group {current_last}:")
            if value != 0:
                print(f"    {name}: {value}")

        # Print D variables grouped by the second last and last indices
        current_second_last = None
        current_last = None
        for name, value in d_vars:
            second_last = name.split('_')[-2]
            last = name.split('_')[-1]
            if second_last != current_second_last:
                current_second_last = second_last
                current_last = None
                print(f"\nD variables for second last group {current_second_last}:")
            if last != current_last:
                current_last = last
                print(f"  Group {current_last}:")
            if value != 0:
                print(f"    {name}: {value}")


if __name__ == "__main__":

    with open('custom/topology_learn/test_topo.json', 'r') as file:
        data = json.load(file)

    topo = data['topologies'][1]
    
    nodes = topo['nodes']
    links = [(link[0], link[1]) for link in topo['links']]
    commodities = [(demand['source'], demand['destinations'], demand['demand']) for demand in topo['demands']] 
    trees = 2
    capacities = {}
    for link, capa in topo['capacities'].items():
        node1, node2 = link.split('-')
        capacities[(node1, node2)] = capa  

    print("---------start----------")

    # 創建並運行優化器
    optimizer = MultiCommodityFlowProblem(nodes, links, commodities, capacities, trees)
    optimizer.add_constraints()
    optimizer.solve()
    optimizer.get_solve()