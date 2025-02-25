import networkx as nx

class NetworkGraph:
    def __init__(self):
        """ 初始化 NetworkX 圖 """
        self.graph = nx.Graph()

    def initialize_graph(self):
        """ 初始化整個網路拓撲 """
        self.graph.clear()  # 清空舊圖

    def add_link(self, u, v, weight=1):
        """ 添加一條鏈路到 NetworkX 拓撲圖 """
        self.graph.add_edge(u, v, weight=weight)

    def del_link(self, u, v):
        """ 刪除特定鏈路 (u, v) """
        if self.graph.has_edge(u, v):
            self.graph.remove_edge(u, v)
            print(f"刪除鏈路: {u} <-> {v}")
        else:
            print(f"鏈路 {u} <-> {v} 不存在")

    def del_node(self, u):
        """ 刪除某個 Switch（包含所有相關鏈路） """
        if self.graph.has_node(u):
            self.graph.remove_node(u)
            print(f"刪除 Switch: {u}，以及與其相關的所有鏈路")
        else:
            print(f"Switch {u} 不存在")

    def dijkstra(self, src, dst):
        """ 使用 Dijkstra 找出最短路徑 """
        try:
            path = nx.shortest_path(self.graph, source=src, target=dst, weight="weight")
            length = nx.shortest_path_length(self.graph, source=src, target=dst, weight="weight")
            return path, length
        except nx.NetworkXNoPath:
            return None, None

    def get_next_hop(self, path):
        """ 取得 Switch 的下一跳表 """
        next_hop = {}
        for i in range(len(path) - 1):
            next_hop[path[i]] = path[i + 1]
        return next_hop
