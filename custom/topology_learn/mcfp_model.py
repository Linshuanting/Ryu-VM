from pulp import LpProblem, LpVariable, lpSum, LpMaximize, value
import json

class MCFPOptimizer:
    def __init__(self, nodes, links, demands):
        """
        初始化 MCFP 優化器
        :param nodes: 拓撲中的節點列表
        :param links: 拓撲中的邊列表
        :param demands: 商品的需求信息，格式為 [(source, [destinations], demand)]
        """
        self.nodes = nodes
        self.links = links
        self.demands = demands
        self.model = None
        self.solution = {}

    def create_mcfp_model(self):
        """創建 MCFP 的 MILP 模型"""
        prob = LpProblem("MCFP", LpMaximize)
        
        # 定義變量
        f = {}  # 流量變量
        Z = LpVariable("Z", lowBound=0)  # 最小注入流量百分比

        # 為每條邊和每個商品定義流量變量
        for (i, j) in self.links:
            for k in range(len(self.demands)):  # demands 是商品的需求列表
                f[(i, j, k)] = LpVariable(f"f_{i}_{j}_{k}", lowBound=0)

        # 目標函數：最大化 Z
        prob += Z, "Maximize the minimum percentage of receiving flow over demand"

        # 流量守恒約束
        for k, (s_k, T_k, d_k) in enumerate(self.demands):
            # 來源節點的流量守恒
            prob += lpSum([f[(s_k, v, k)] for v in self.nodes if (s_k, v) in self.links]) >= d_k * Z , f"Flow conservation at source {s_k} for commodity {k}"
            
            # 目的地節點的流量守恒，並且計算接收百分比
            for t in T_k:
                prob += lpSum([f[(v, t, k)] for v in self.nodes if (v, t) in self.links]) >= d_k * Z, f"Flow to destination {t} for commodity {k}"
                prob += lpSum([f[(v, t, k)] for v in self.nodes if (v, t) in self.links]) <= d_k, f"Flow upper bound at destination {t} for commodity {k}"
            
            # 中間節點的流量守恒
            for v in self.nodes:
                if v != s_k and v not in T_k:
                    # 對每個中間節點 v，進入的流量 <= 傳出的流量總和 (確保 multicast)
                    prob += (lpSum([f[(u, v, k)] for u in self.nodes if (u, v) in self.links]) <=
                             lpSum([f[(v, w, k)] for w in self.nodes if (v, w) in self.links])), f"Flow conservation at node {v} for commodity {k}"

                     # 找到進入和傳出該節點的邊
                    input_links = [(u, v) for u in self.nodes if (u, v) in self.links]  # 進入邊
                    output_links = [(v, w) for w in self.nodes if (v, w) in self.links]  # 傳出邊

                    # 如果該節點有進入邊且有傳出邊
                    if input_links and output_links:
                        # 計算進入邊的總流量
                        total_input_flow = lpSum([f[(u, v, k)] for (u, v) in input_links])

                        # 對於每條傳出邊，設置流量不超過進入邊的總流量
                        for (v, w) in output_links:
                            prob += f[(v, w, k)] <= total_input_flow, f"Multicast constraint at node {v} for commodity {k} to {w}"
                            
                
                if v == s_k:
                    prob += lpSum([f[(u, v, k)] for u in self.nodes if (u, v) in self.links]) == 0, f"Start node {v} in commodity {k} inflow is Zero "
            
            

        # 邊容量約束，同時處理單向和雙向情況
        for (u, v) in self.links:
            if (v, u) in self.links:  # 雙向邊
                if u < v:  # 確保每對邊只處理一次
                    if (u.startswith('c') or v.startswith('c') ):
                        prob += lpSum([f[(u, v, k)] + f[(v, u, k)] for k in range(len(self.demands))]) <= 50, f"Capacity constraint for biidirectional link {u}->{v}"
                    else:
                        prob += lpSum([f[(u, v, k)] + f[(v, u, k)] for k in range(len(self.demands))]) <= 10, f"Capacity constraint for bidirectional link {u}<->{v}"
            else:  # 單向邊
                if (u.startswith('c') or v.startswith('c') ):
                    prob += lpSum([f[(u, v, k)] for k in range(len(self.demands))]) <= 50, f"Capacity constraint for unidirectional link {u}->{v}"
                else:
                    prob += lpSum([f[(u, v, k)] for k in range(len(self.demands))]) <= 10, f"Capacity constraint for unidirectional link {u}->{v}"

        self.model = prob
        return prob

    def solve(self):
        """求解 MILP 問題並返回解決方案"""
        if self.model is None:
            raise ValueError("Model has not been created. Call create_mcfp_model first.")
        
        self.model.solve()
        
        # 收集結果
        solution = {}
        for v in self.model.variables():
            solution[v.name] = value(v)

        self.solution = solution
        
        return solution
    
    def get_solve(self):

        print("------ Solution -------")
        for k, v in self.solution.items():
            if v != 0.0 or k is 'Z':
                print(f"{k}: {v}")


# 示例使用
if __name__ == "__main__":
    
    with open('custom/topology_learn/test_topo.json', 'r') as file:
        data = json.load(file)
    
    # 假設的拓撲信息
    topo = data['topologies'][0]
    add_demands = data['additional_demands'][0]

    print(f"Topology: {topo['name']}")
    nodes = topo['nodes']
    
    links = [(link[0], link[1]) for link in topo['links']]
    demands = [(demand['source'], demand['destinations'], demand['demand']) for demand in topo['demands']]

    print(nodes)
    print(links)
    print(demands)
    print("----- starts -----")

    # 創建並運行優化器
    optimizer = MCFPOptimizer(nodes, links, demands)
    optimizer.create_mcfp_model()
    solution = optimizer.solve()

    
    print("Solution:", solution)

    print("------ Solution -------")
    for k, v in solution.items():
        if v != 0.0 or k is 'Z':
            print(f"{k}: {v}")


