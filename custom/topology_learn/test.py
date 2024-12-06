from pulp import LpProblem, LpVariable, lpSum, LpMaximize, LpStatus, value

class DantzigWolfeDecomposition:
    def __init__(self, nodes, links, commodities, capacities, trees):
        """
        Initialize Dantzig-Wolfe decomposition.
        :param nodes: List of nodes in the graph.
        :param links: List of tuples representing links (u, v).
        :param commodities: List of tuples (source, destinations, demand).
        :param capacities: Dictionary of capacities for each link (u, v).
        :param trees: Number of spanning trees.
        """
        self.nodes = nodes
        self.links = links
        self.commodities = commodities
        self.capacities = capacities
        self.trees = trees
        self.master_problem, self.Z, self.theta = self.create_master_problem()
        self.subproblems = self.create_subproblems()

    def create_master_problem(self):
        """
        Create the master problem.
        :return: Master problem, Z variable, theta variables.
        """
        master_problem = LpProblem("MasterProblem", LpMaximize)

        # Z variable (global objective)
        Z = LpVariable("Z", lowBound=0, upBound=1)

        # Theta variables (columns from subproblems)
        theta = {k: LpVariable(f"theta_{k}", lowBound=0) for k, _ in enumerate(self.commodities)}

        # Objective function
        master_problem += Z, "ObjectiveFunction"

        # Constraints linking Z and theta
        for k in range(len(self.commodities)):
            master_problem += Z <= theta[k], f"Constraint_Z_{k}"

        return master_problem, Z, theta

    def create_subproblems(self):
        """
        Create subproblems for each commodity and spanning tree.
        :return: Dictionary of subproblems.
        """
        subproblems = {}
        for k, (source, destinations, demand) in enumerate(self.commodities):
            for c in range(self.trees):
                subproblems[(k, c)] = self.create_subproblem(k, source, destinations, demand, c)
        return subproblems

    def create_subproblem(self, k, source, destinations, demand, tree):
        """
        Create a subproblem for a specific commodity and tree.
        :param k: Commodity index.
        :param source: Source node.
        :param destinations: List of destination nodes.
        :param demand: Demand value.
        :param tree: Tree index.
        :return: Subproblem.
        """
        subproblem = LpProblem(f"Subproblem_{k}_{tree}", LpMaximize)

        # Flow variables for each edge
        flow = {link: LpVariable(f"f_{link[0]}_{link[1]}_{k}_{tree}", lowBound=0) for link in self.links}

        # Binary variable for edge selection in spanning tree
        x = {link: LpVariable(f"x_{link[0]}_{link[1]}_{k}_{tree}", lowBound=0, upBound=1, cat="Binary") for link in self.links}

        # Descendant variables for spanning tree
        D = {link: LpVariable(f"D_{link[0]}_{link[1]}_{k}_{tree}", lowBound=0, cat="Integer") for link in self.links}

        # Objective: Maximize flow from source
        subproblem += lpSum(flow[(source, v)] for v in self.nodes if (source, v) in self.links), "MaximizeSourceFlow"

        # Flow conservation constraints
        for v in self.nodes:
            if v != source and v not in destinations:
                subproblem += (
                    lpSum(flow[(u, v)] for u in self.nodes if (u, v) in self.links) 
                    == lpSum(flow[(v, w)] for w in self.nodes if (v, w) in self.links)
                ), f"FlowConservation_{v}_{k}_{tree}"

        # Multicast constraints
        for v in destinations:
            subproblem += (
                lpSum(flow[(u, v)] for u in self.nodes if (u, v) in self.links) >= demand
            ), f"MulticastConstraint_{v}_{k}_{tree}"

        # Descendant constraints
        for u, v in self.links:
            subproblem += D[(u, v)] <= (len(self.nodes) - 1) * x[(u, v)], f"DescendantConstraint_{u}_{v}_{k}_{tree}"

        # Capacity constraints
        for u, v in self.links:
            subproblem += flow[(u, v)] <= x[(u, v)] * self.capacities[(u, v)], f"CapacityConstraint_{u}_{v}_{k}_{tree}"

        return subproblem

    def solve(self):
        """
        Solve the Dantzig-Wolfe decomposition.
        """
        iteration = 0
        while True:
            print(f"Iteration {iteration}: Solving master problem...")
            self.master_problem.solve()
            print(f"Master Problem Status: {LpStatus[self.master_problem.status]}")

            # Check convergence
            if self.check_convergence():
                break

            print("Solving subproblems...")
            for (k, c), subproblem in self.subproblems.items():
                subproblem.solve()
                print(f"Subproblem ({k}, {c}) Status: {LpStatus[subproblem.status]}")

                # Generate column for master problem
                self.generate_column(k, c, subproblem)

            iteration += 1

        # Print final solution
        self.print_solution()

    def check_convergence(self):
        """
        Check if the master problem has converged.
        :return: True if converged, False otherwise.
        """
        # 获取主问题的当前目标值
        master_obj = value(self.master_problem.objective)

        # 检查子问题是否可以提供改进的列
        for (k, c), subproblem in self.subproblems.items():
            reduced_cost = self.calculate_reduced_cost(k, c, subproblem)
            if reduced_cost < 0:  # 如果有子问题的 reduced cost 为负，尚未收敛
                return False

        # 如果没有新的列生成，或者目标值不再变化，则收敛
        return True

    def generate_column(self, k, c, subproblem):
        """
        Generate a new column for the master problem from the subproblem solution.
        :param k: Commodity index.
        :param c: Tree index.
        :param subproblem: Solved subproblem.
        """
        # 提取子问题的解
        solution = {var.name: value(var) for var in subproblem.variables()}
        theta_value = solution[f"theta_{k}_{c}"]

        # 提取子问题的边使用情况
        edges_used = [(u, v) for u, v in self.links if solution.get(f"x_{u}_{v}_{k}_{c}", 0) > 0]

        # 将新列添加到主问题
        self.master_problem += (
            self.theta[k] + lpSum(self.Z * theta_value) >= 0
        ), f"NewColumn_{k}_{c}"
    
    def calculate_reduced_cost(self, k, c, subproblem):
        """
        Calculate the reduced cost for a subproblem.
        :param k: Commodity index.
        :param c: Tree index.
        :param subproblem: Solved subproblem.
        :return: Reduced cost value.
        """
        if subproblem.status != 1:  # 确保子问题求解成功
            return None

        # 提取主问题的对偶变量值
        dual_values = {constraint.name: constraint.pi for constraint in self.master_problem.constraints.values()}

        # 子问题目标值
        subproblem_obj = value(subproblem.objective)

        # 计算 reduced cost
        reduced_cost = subproblem_obj
        for constraint_name, dual_value in dual_values.items():
            if constraint_name in subproblem.constraints:
                reduced_cost -= dual_value * value(subproblem.constraints[constraint_name].slack)

        return reduced_cost

    def print_solution(self):
        """
        Print the final solution of the master problem.
        """
        print("Final Solution:")
        for var in self.master_problem.variables():
            print(f"{var.name} = {value(var)}")

# Example usage
nodes = ["A", "B", "C", "D"]
links = [("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")]
commodities = [("A", ["D"], 20)]
capacities = {("A", "B"): 15, ("A", "C"): 10, ("B", "C"): 20, ("C", "D"): 25}
trees = 2

optimizer = DantzigWolfeDecomposition(nodes, links, commodities, capacities, trees)
optimizer.solve()
