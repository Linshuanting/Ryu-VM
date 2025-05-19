from typing import List, Dict, Tuple, Set
import re

class myAlgorithm:

    def __init__(self, nodes, link_capacities={}, commodities=None) -> None:
        
        self.nodes = set(nodes)
        self.capacities = {tuple(re.split(r'[,-]', link)): value for link, value in link_capacities.items()}
        self.commodities = commodities
    
    def run(self, R1:int, R2:int) -> Dict[str, List[Dict[Tuple[str, str], float]]]:

        nodes = self.nodes
        capacities = self.capacities
        commodities = self.commodities

        return self.greedy(nodes, capacities, commodities, R1, R2)

    def greedy(
            self, 
            V: Set[str], 
            E: Dict[Tuple[str, str], float], 
            K: List[Dict],
            R1: int, 
            R2: int
        ) -> Dict[str, List[Dict[Tuple[str, str], float]]]:
        
        Res = {}

        for k in K:
            flow = []
            k_demand = k['demand']
            k_src = k['source']
            k_dest = k['destinations']
            k_name = k['name']

            lower_bound = k_demand/R1
            filtered_E = {e:E[e] for e in E if E[e] >= lower_bound}

            # print(f"the name: {k_name}")
            # print(f"phase 1")
            # print(f"filtered_E: {filtered_E}")

            while k_demand > 0:
                
                tree = self.build_spanning_tree(V, filtered_E, k_src)
                # self.print_data(tree)
                if(self.is_connect_tree(tree, k_src, k_dest) is False):
                    # print(f"{k_name} in phase 1 build an unconnecting tree")
                    break
                
                k_demand, path = self.decrease_bandwidth(k_src, k_dest, k_demand, tree, filtered_E)
                # self.add_path_to_result(path, flow)
                self.add_path_respectively_to_result(path, flow)
                self.delete_redundant_edge(lower_bound, filtered_E, path)

                # print(f"current flow in algorithm: {flow}, current demand:{k_demand}")

            self.update_E(E, flow)
            #  print(f"中斷點一")
            if (k_demand == 0): 
                Res[k_name] = flow
                continue
            #  print(f"中斷點二")

            # print(f"phase 2")

            for i in range(R2):
                tree = self.build_spanning_tree(V, E, k_src)
                
                if (self.is_connect_tree(tree, k_src, k_dest) is False):
                    # print(f"{k_name} in phase 2 build an unconnecting tree")
                    break
                
                k_demand, path = self.decrease_bandwidth(k_src, k_dest, k_demand, tree, E)
                
                # self.add_path_to_result(path, flow)
                self.add_path_respectively_to_result(path, flow)
                self.delete_redundant_edge(0, E, path)
                # print(f"中斷點三")
                if k_demand == 0:
                    break

                # print(f"中斷點四")

            # print(f"中斷點五")
            Res[k_name] = flow

            if k_demand != 0:
                return Res
        
        # print(f"the remaining graph is")
        # self.print_data(E)
        # print(f"中斷點六")
        return Res

    def add_path_to_result(
            self, 
            path:Dict[Tuple[str, str], float], 
            res:Dict[Tuple[str, str], float]):

        for (u, v), w in path.items():
            if (u, v) in res:
                res[(u, v)] += w
            else:
                res[(u, v)] = w
    
    def add_path_respectively_to_result(
            self, 
            path:Dict[Tuple[str, str], float],
            res:List[Dict[Tuple[str, str], float]]
    ):
        res.append(path)

    def build_spanning_tree(self, V:Set[str], E:Dict[Tuple[str, str], float], src:str) -> Dict[Tuple[str, str], float]:
        st = ST(V, E)
        st.turn_negative_edge()
        tree = st.build_by_prim(src)
        # print(f"prim algorithm result: {tree}")
        st.turn_negative_edge()
        return st.turn_negative_edge(tree)

    def is_connect_tree(self, tree:Dict[Tuple[str, str], float], src:str, dsts:Set[str]) -> bool:
        
        connected_nodes = set()
        
        for u, v in tree.keys():
            connected_nodes.add(u)
            connected_nodes.add(v)

        if src not in connected_nodes:
            return False

        for dst in dsts:
            if dst not in connected_nodes:
                return False

        return True
            
    def decrease_bandwidth(
            self, 
            src:str, 
            dsts:Set[str],
            demand:float, 
            tree:Dict[Tuple[str,str], float],
            E:Dict[Tuple[str, str], float]
        ) -> Tuple[float, Dict[Tuple[str, str], float]] :

        """
        Decrease the using bandwidth with MST and return the bandwidth the remaining needing

        :param src: the start point of commodity 
        :param dsts: all of the commodity destinations
        :param demand: amount of the commodity need
        :param tree: MST tree and the bandwidth each link having
        :param E: the total graph and the bandwidth each link having
        :return: A tuple (remaning demand, the using path (a part of spanning tree) and using demand)
        """
        
        adjacency_list = self.tree_to_adjacency_list(tree)

        low_demand, path, is_on_path = self.dfs_tree(src, dsts, adjacency_list, E)

        if low_demand > demand:
            low_demand = demand
        
        for u, v in path:
            E[(u, v)] = E[(u, v)] - low_demand
        
        path_dict = {}

        for u, v in path:
            path_dict[(u, v)] = low_demand

        return demand-low_demand, path_dict

    def tree_to_adjacency_list(self, tree: Dict[Tuple[str, str], float]) -> Dict[str, List[str]]:
        
        """
        Convert a tree represented as a dictionary of edges into an adjacency list.

        :param tree: The tree represented as { (u, v): weight, ... }.
        :return: Adjacency list representation { u: [(v, weight), ...], ... }.
        """
        adjacency_list = {}

        # Iterate through each edge in the tree
        for u, v in tree.keys():
            # Add edge u -> v
            if u not in adjacency_list:
                adjacency_list[u] = []
            adjacency_list[u].append(v)

        return adjacency_list

    # capacity, using edge in tree
    def dfs_tree(
            self,
            src:str, 
            dsts:Set[str], 
            tree:Dict[str, List[str]], 
            capacity:Dict[Tuple[str, str], float]
        ) -> Tuple[float, Set[Tuple[str, str]], bool]:

        """
        Depth-first search on a tree represented as a dictionary.

        :param src: Source node as a string.
        :param dsts: Set of destination nodes as strings.
        :param tree: The tree represented as a dictionary {node: [children]}.
        :param capacity: Dictionary of edge capacities {(u, v): capacity}.
        :return: A tuple (low_demand, path, dst_num_on_path).
        """
        
        low_demand = float('inf')
        path = set()
        is_on_path = False
        for node in tree.get(src, []):
            is_next_node_on_path = False

            demand, sub_path, is_next_node_on_path = self.dfs_tree(node, dsts, tree, capacity)

            edge_bandwidth = capacity[(src, node)]

            if node in dsts:
                is_next_node_on_path = True
                
            if is_next_node_on_path:
                is_on_path = True
                path.add((src, node))
                path.update(sub_path)
            
            if is_next_node_on_path and demand < low_demand:
                low_demand = demand

            if is_next_node_on_path and edge_bandwidth < low_demand:
                low_demand = edge_bandwidth

        return low_demand, path, is_on_path
    
    def print_data(self, d:Dict[Tuple[str, str], float] = None, s:Set[Tuple[str, str]] = None):

        if d is not None:
            for (u, v), w in d.items():
                print(f"link: {u}-{v}, bandwidth:{w}")
        elif s is not None:
            for (u, v) in s:
                print(f"link: {u}-{v}")
        else:
            return
        
        print("------ print data finish ----------")
    
    def print_result(self, result: Dict[str, List[Dict[Tuple[str, str], float]]]):

        print(f"--- print result ---")
        for name, lists in result.items():
            print(f"name: {name}")
            for res in lists:
                for (u, v), w in res.items():
                    print(f"link: {u}-{v}, bandwidth:{w}")
                print("-----------------")

    def get_throughput(self, result: Dict[str, List[Dict[Tuple[str, str], float]]]):
        commodity_throughput = []
        for name, list in result.items():
            throughput = []
            for res in list:
                for(u, v), w in res.items():
                    throughput.append(w)
                    break
            commodity_throughput.append(throughput)
        
        return commodity_throughput

    def update_E(self, E:Dict[Tuple[str, str], float], paths:List[Dict[Tuple[str, str], float]]):
        for path in paths:
            for (u, v), w in path.items():
                E[(u, v)] = E[(u, v)] - w

                if E[(u, v)] <= 0:
                    del E[(u, v)]
            
    
    def delete_redundant_edge(self, lowerbound:float, E:Dict[Tuple[str, str], float], path:Dict[Tuple[str, str], float]):
        for edge, w in path.items():
            if E[edge] < lowerbound or E[edge] == 0:
                del E[edge]
    
    def set_default_commodity(self, src, dsts):
        commodity_data = {
            "name": "default_commodity",
            "source": src,
            "destinations": dsts,
            "demand": 1
        }

        if self.commodities is None:
            self.commodities = []

        self.commodities.append(commodity_data)
    
    def set_default_capacity_link(self, links):
        new_links = {}
        for (u, v) in links:
            new_links[(u, v)] = 1
        
        self.capacities = new_links

    def get_default_commodity_name(self):
        return "default_commodity"

    
class ST:

    def __init__(self, V:Set[str], E:Dict[Tuple[str, str], float]) -> None:
        self.V = V
        self.E = E

    def turn_negative_edge(self, E:Dict[Tuple[str, str], float] = None) -> Dict[Tuple[str, str], float]:
        
        E = E if E is not None else self.E
        
        for edge in E:
            if E[edge] is not float('inf'):
                E[edge] = -E[edge]
        return E
    
    def create_adjacency_matrix(self) -> Tuple[List[List[float]], Dict[str, int], Dict[int, str]]:
        node_idx = {node: i for i, node in enumerate(self.V)}
        idx_node = {i: node for node, i in node_idx.items()}
        size = len(self.V)

        matrix = [[float('inf')] * size for _ in range(size)]
        for i in range(size):
            matrix[i][i] = 0
        
        for (u, v), w in self.E.items():
            i, j = node_idx[u], node_idx[v]
            matrix[i][j] = w
            
        return matrix, node_idx, idx_node
    
    
    def build_by_prim(self, src: str) -> Dict[Tuple[str, str], float]:
        
        graph, node_idx, idx_node = self.create_adjacency_matrix()
        
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

            if parent[u] != -1 and u != -1:
                p, v = idx_node[parent[u]], idx_node[u]
                mst[(p, v)] = graph[parent[u]][u]
            elif u == node_idx[src]:
                pass
            else:
                break
            
            for v in range(size_of_V):
                if graph[u][v] != float('inf') and not visit[v] and graph[u][v] < key[v]:
                    key[v] = graph[u][v]
                    parent[v] = u

        return mst
            
