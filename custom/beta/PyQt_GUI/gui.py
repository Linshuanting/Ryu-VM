import sys, os
import json
import requests
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from beta.tools.commodity_parser import commodity_parser as cm_parser
from beta.tools.utils import to_dict
from gui_tools import get_bandwidth, get_commodity, run_algorithm

# Ryu 控制器 REST API
RYU_API_URL = "http://localhost:8080/topology"  # 查詢交換機 1 的流表

class RyuFlowMonitor(QWidget):
    def __init__(self):
        super().__init__()

        self.latest_links = None  # 存储最新的 links 数据
        self.latest_nodes = None  # 存储最新的 nodes 数据

        self.initUI()
        self.start_auto_fetch()  # 自动定时 fetch data

    def initUI(self):
        # 设置窗口标题
        self.setWindowTitle("Ryu Flow Table Monitor")
        self.setGeometry(100, 100, 1000, 600)  # 调整窗口大小

        # 创建 Layout
        main_layout = QVBoxLayout()

        # 创建 "Links" 和 "Hosts" 显示区域
        data_layout = QHBoxLayout()
        self.links_text = QTextEdit()
        self.links_text.setReadOnly(True)
        self.hosts_text = QTextEdit()
        self.hosts_text.setReadOnly(True)

        data_layout.addWidget(QLabel("Links"))
        data_layout.addWidget(self.links_text)
        data_layout.addWidget(QLabel("Hosts"))
        data_layout.addWidget(self.hosts_text)

        # 创建 "Algorithm Output" 显示区域
        algo_layout = QVBoxLayout()
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)

        # 创建 "Run Algorithm" 按钮
        self.run_button = QPushButton("Run Algorithm")
        self.run_button.clicked.connect(self.run_algorithm_process)

        # 添加到布局
        main_layout.addLayout(data_layout)
        main_layout.addWidget(QLabel("Algorithm Output"))
        main_layout.addWidget(self.result_text)
        main_layout.addWidget(self.run_button)

        self.setLayout(main_layout)

    def start_auto_fetch(self):

        self.fetch_data()  # 立即执行一次获取数据

        """ 启动定时器，每隔 5 秒自动 fetch data """
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data)
        self.timer.start(15000)  # 5000ms = 5秒

    def fetch_data(self):
        try:
            # 这里替换成你的 Ryu REST API URL
            url = RYU_API_URL
            response = requests.get(url)
            data = response.json()

            # 解析 `links` 数据
            links_data = data.get("links", {})

            formatted_links = []
            parsed_links = []

            nodes_set = set()  # 存储 nodes，避免重复

            for key, value in links_data.items():
                # 分割 key 和 value
                src_device, dst_device = key.rsplit("-", 1)  # 源设备
                src_port, dst_port = value.rsplit("-", 1)  # 目标设备

                nodes_set.add(src_device)
                nodes_set.add(dst_device)

                # 设备类型检查
                src_is_host = src_device.startswith("h")
                dst_is_host = dst_device.startswith("h")

                src_type = "Host" if src_is_host else "Switch"
                dst_type = "Host" if dst_is_host else "Switch"

                src_formatted = f"{src_type} {src_device} (eth{src_port})"
                dst_formatted = f"{dst_type} {dst_device} (eth{dst_port})"

                # **排序规则**：Host (h) 设备在前，Switch (s) 设备在后
                def get_sort_key(device):
                    if device.startswith("h"):
                        # **对于 `hffff` 这样的非数字主机，保持原始名称**
                        try:
                            return (0, int(device[1:]))  # `h1`, `h2`, `h3` 正常转换
                        except ValueError:
                            return (0, float("inf"))  # `hffff` 作为字符串排序
                    else:
                        return (1, int(device))  # Switch `sX` 仍然使用数字排序

                src_sort_key = get_sort_key(src_device)
                dst_sort_key = get_sort_key(dst_device)

                # 存储解析后的数据和排序键
                parsed_links.append(((src_sort_key, dst_sort_key), f"{src_formatted} → {dst_formatted}"))

            # **按排序规则排序**
            parsed_links.sort(key=lambda x: (x[0][0], x[0][1]))

            # 提取排序后的数据
            formatted_links = [entry[1] for entry in parsed_links]

            # 解析 `hosts` 数据
            hosts = {key: value for key, value in data.get("hosts", {}).items()}
            hosts_data = json.dumps(data.get("hosts", {}), indent=4, ensure_ascii=False)

            self.latest_links = links_data
            self.latest_nodes = list(sorted(nodes_set))

            links_len = len(links_data) - len(hosts)*2
            print(f"switch links amount: {links_len}")

            # 更新 GUI 文本框
            self.links_text.setPlainText("\n".join(formatted_links))
            self.hosts_text.setPlainText(hosts_data)


        except Exception as e:
            self.links_text.setPlainText(f"数据获取失败: {e}")
            self.hosts_text.setPlainText(f"数据获取失败: {e}")
    
    def run_algorithm_process(self):
        """ 运行 `run_algorithm()` 并显示结果 """
        try:
            
            if self.latest_links is None or self.latest_nodes is None:
                self.result_text.setPlainText("错误: 还未获取到数据，等待自动 fetch 完成")
                return
            
            links = self.latest_links
            nodes = self.latest_nodes

            print(f"link: {links}")

            capacities = get_bandwidth(links)
            commodities = get_commodity(nodes, 2)

            print(f"commodites: {commodities}")

            res = run_algorithm(nodes, links, capacities, commodities)

            print(res)

            parser = cm_parser()
            packet = parser.serialize(res, commodities)

            # 将结果转换为格式化 JSON 并显示
            output_text = json.dumps(packet, indent=4, ensure_ascii=False)
            self.result_text.setPlainText(output_text)

        except Exception as e:
            self.result_text.setPlainText(f"运行失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RyuFlowMonitor()
    window.show()
    sys.exit(app.exec_())

