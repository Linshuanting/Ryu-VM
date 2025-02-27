from PyQt5.QtCore import QThread, pyqtSignal
import requests
import json
from beta.tools.utils import tuple_key_to_str
from beta.tools.commodity_parser import commodity_parser as cm_parser
from beta.PyQt_GUI.gui_tools import get_bandwidth, get_commodity, run_algorithm

class RestAPIClient:
    def __init__(self, url):
        self.url = url
        self.latest_links = None
        self.latest_nodes = None
        self.worker = None
        self.upload_worker = None
        self.fetch_worker = None

    def run_algorithm_process(self, result_text):
        if self.latest_links is None or self.latest_nodes is None:
            result_text.setPlainText("❌ 错误: 还未获取到数据，等待自动 fetch 完成")
            return

        result_text.setPlainText("🚀 Running algorithm...")
        self.worker = AlgorithmWorker(self.latest_nodes, self.latest_links)
        self.worker.finished.connect(lambda commodities, res: self.on_algorithm_finished(commodities, res, result_text))
        self.worker.error.connect(lambda err: result_text.setPlainText(f"⚠ 运行失败: {err}"))
        self.worker.start()

    def on_algorithm_finished(self, commodities, result, result_text):
        try:
            parser = cm_parser()
            packet = []
            for com in commodities:
                commodity = parser.serialize_commodity(
                    name=com["name"],
                    src=com["source"],
                    dsts=com["destinations"],
                    demand=com["demand"],
                    paths=result.get(com["name"], [])
                )
                packet = parser.add_packet(commodity, packet)

            output_text = json.dumps(packet, indent=4, ensure_ascii=False)

            self.upload_commodity_data(output_text, result_text)
        
        except Exception as e:
            result_text.setPlainText(f"⚠ 结果处理失败: {str(e)}")

    def upload_commodity_data(self, data, result_text):
        result_text.setPlainText(f"📡 Uploading data to server...\n{data}")
        self.upload_worker = UploadWorker(self.url, data)
        self.upload_worker.finished.connect(lambda res: self.on_upload_finished(res, result_text, data))
        self.upload_worker.error.connect(lambda err: result_text.setPlainText(f"⚠ 上傳失敗: {err}"))
        self.upload_worker.start()

    def on_upload_finished(self, response, result_text, data):
        result_text.setPlainText(f"✅ Upload finished:{response}\n{data}")

    def fetch_topology_data(self, links_text, hosts_text):
        self.fetch_worker = FetchWorker(self.url)
        self.fetch_worker.finished.connect(lambda data: self.on_fetch_finished(data, links_text, hosts_text))
        self.fetch_worker.error.connect(lambda err: links_text.setPlainText(f"数据获取失败: {err}"))
        self.fetch_worker.start()

    def on_fetch_finished(self, data, links_text, hosts_text):
        try:
            
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
            links_text.setPlainText("\n".join(formatted_links))
            hosts_text.setPlainText(hosts_data)
        
        except Exception as e:
            links_text.setPlainText(f"数据解析失败: {e}")
            hosts_text.setPlainText(f"数据解析失败: {e}")

class AlgorithmWorker(QThread):
    finished = pyqtSignal(list, dict)
    error = pyqtSignal(str)

    def __init__(self, nodes, links):
        super().__init__()
        self.nodes = nodes
        self.links = links

    def run(self):
        try:
            print("🚀 Running algorithm in background thread...")
            capacities = get_bandwidth(self.links)
            input_commodities = get_commodity(self.nodes, 2)
            result = run_algorithm(self.nodes, self.links, capacities, input_commodities)
            self.finished.emit(input_commodities, result)
        except Exception as e:
            self.error.emit(str(e))


class UploadWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, data):
        super().__init__()
        self.url = url
        self.data = data

    def run(self):
        try:
            json_data = self.data if isinstance(self.data, str) else json.dumps(self.data, indent=4)
            headers = {'Content-Type': 'application/json'}
            print(f"📤 Uploading Data to {self.url}...")
            response = requests.post(self.url + "/test", data=json_data, headers=headers)
            response.raise_for_status()
            self.finished.emit(response.text)
        except requests.exceptions.RequestException as e:
            self.error.emit(f"❌ Error posting data to API: {e}")


class FetchWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url + "/topology")
            response.raise_for_status()
            self.finished.emit(response.json())
        except requests.exceptions.RequestException as e:
            self.error.emit(f"❌ Error fetching data from API: {e}")