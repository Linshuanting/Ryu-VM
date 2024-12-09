from typing import List, Dict, Tuple, Set

class myAlgorithm:

    def __init__(self, nodes, links, capacities, commodities) -> None:
        
        self.nodes = nodes
        self.links = links
        self.capacities = capacities
        self.commodities = commodities

    def greedy(self, V: Set[str], E: Dict[Tuple[str, str], int], K: List[Dict],
               R1: float, R2: float) -> None:
        
        Res = {}

        for k in K:
            flow = {}
            k_demand = k['demand']
            k_src = k['source']
            k_dest = k['destination']

            lower_bound = k_demand/R1
            filtered_E = {e for e in E if e[2] >= lower_bound}

            while k_demand > 0:
                tree = self.build_spanning_tree(V, filtered_E)


    def build_spanning_tree(self, V:Set[str], E:Set[Tuple[str, str]]) -> Set[Tuple[str, str]]:
        pass

    def is_connect_tree(self, tree:Set[Tuple[str, str]], src:str, dst:Set[str]) -> bool:
        pass


class ST:

    def __init__(self, V:Set[str], E:Dict[Tuple[str, str], float]) -> None:
        self.V = V
        self.E = E

    def turn_negative_edge(self, E:Dict[Tuple[str, str], float]) -> Dict[Tuple[str, str], float]:
        for edge in E:
            if E[edge] is not float('inf'):
                E[edge] = -E[edge]
        return E
    
    def create_adjacency_matrix(self) -> Tuple[List[List[float]], Dict[str, int]]:
        node_idx = {node: i for i, node in enumerate(self.V)}
        size = len(self.V)

        matrix = [[float('inf')] * size for _ in range(size)]
        for i in range(size):
            matrix[i][i] = 0
        
        for (u, v), w in self.E.items():
            i, j = node_idx[u], node_idx[v]
            matrix[i][j] = w
            
        return matrix, node_idx

    # TODO 
    # 需考慮 Graph 有方向性
    def build_by_prim(self, src: str, E:Dict[Tuple[str, str], int]) -> Dict[Tuple[str, str], float]:
        
        graph, node_idx = self.create_adjacency_matrix()
        
        size_of_V = len(self.V)
        # 生成樹倒每個頂點的最小邊權重
        key = [float('inf')] * size_of_V
        # 每個頂點的父節點，用來建構 MST
        parent = [-1] * size_of_V
        # 紀錄每個頂點是否已包含在生成樹中
        visit = [False] * size_of_V
        # 需要的最小生成樹
        mst = {}

        key[node_idx[src]] = 0
        
        for _ in range(size_of_V):

            min_key = float('inf')
            u = -1
            for i in range(size_of_V):
                if not visit[i] and key[i] < min_key:
                    min_key = key[i]
                    u = i
            
            visit[u] = True

            if parent[u] != -1:
                p, v = node_idx[parent[u]], node_idx[u]
                mst[(p, v)] = graph[u][v]
            else:
                break
            
            for v in range(size_of_V):
                if graph[u][v] != float('inf') and not visit[v] and graph[u][v] < key[v]:
                    key[v] = graph[u][v]
                    parent[v] = u

        return mst
            
            

class UnionFind:

    def __init__(self) -> None:
        pass

    def find(self):
        pass
    def union(self):
        pass

