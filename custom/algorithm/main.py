import json
import re
from typing import Dict, Tuple, List, Set
from greedy import myAlgorithm  # 替换为你的主代码文件名

def load_test_data(filename: str) -> Dict:
    """
    Load test data from a JSON file.

    :param filename: Path to the JSON file.
    :return: Dictionary containing the test data.
    """
    with open(filename, 'r') as file:
        return json.load(file)

def convert_json_to_inputs(topo: Dict) -> Tuple[Set[str], Dict[Tuple[str, str], float], List[Dict]]:
    """
    Convert JSON data to the required format for myAlgorithm.

    :param data: Test data loaded from the JSON file.
    :return: Tuple of nodes, edges, capacities, and commodities.
    """
    data = topo['topologies'][3]
    nodes = set(data["nodes"])
    links = data["links"]
    capacities = {tuple(re.split(r'[,-]', link)): value for link, value in data["capacities"].items()}
    commodities = data["commodities"]
    return nodes, links, capacities, commodities

def main():
    # Load test data from JSON file
    data = load_test_data("test_data.json")

    # Convert data to algorithm input format
    nodes, links, capacities, commodities = convert_json_to_inputs(data)

    # Instantiate myAlgorithm class
    algorithm = myAlgorithm(nodes, links, capacities, commodities)

    # Execute the algorithm's greedy method
    res = algorithm.greedy(
        V=nodes,
        E=capacities,
        K=commodities,
        R1=2,  # Example R1 value
        R2=3   # Example R2 value
    )

    algorithm.print_result(res)
    

if __name__ == "__main__":
    main()
