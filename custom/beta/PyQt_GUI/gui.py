import sys
import os
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from beta.PyQt_GUI.rest_client import RestAPIClient

# Ryu 控制器 REST API
RYU_API_URL = "http://localhost:8080"

class RyuFlowMonitor(QWidget):
    def __init__(self):
        super().__init__()

        self.client = RestAPIClient(RYU_API_URL)  # REST API 客戶端
        self.initUI()
        self.start_auto_fetch()

    def initUI(self):
        """ 初始化 UI """
        self.setWindowTitle("Ryu Flow Table Monitor")
        self.setGeometry(100, 100, 1000, 600)

        # 設定主 Layout
        main_layout = QVBoxLayout()

        # 建立 Link & Hosts 顯示區域
        data_layout = QHBoxLayout()
        self.links_text = QTextEdit(readOnly=True)
        self.hosts_text = QTextEdit(readOnly=True)

        data_layout.addWidget(QLabel("Links"))
        data_layout.addWidget(self.links_text)
        data_layout.addWidget(QLabel("Hosts"))
        data_layout.addWidget(self.hosts_text)

        # Algorithm Output 區域
        self.result_text = QTextEdit(readOnly=True)

        # Algorithm 運行按鈕
        self.run_button = QPushButton("Run Algorithm")
        self.run_button.clicked.connect(self.run_algorithm)

        # 組合所有元件
        main_layout.addLayout(data_layout)
        main_layout.addWidget(QLabel("Algorithm Output"))
        main_layout.addWidget(self.result_text)
        main_layout.addWidget(self.run_button)

        self.setLayout(main_layout)

    def start_auto_fetch(self):
        """ 啟動定時器，每 15 秒自動獲取拓撲數據 """
        self.client.fetch_topology_data(self.links_text, self.hosts_text)  # 立即獲取一次數據
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.client.fetch_topology_data(self.links_text, self.hosts_text))
        self.timer.start(15000)  # 15秒刷新一次

    def run_algorithm(self):
        """ 觸發 Algorithm 運行 """
        self.client.run_algorithm_process(self.result_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RyuFlowMonitor()
    window.show()
    sys.exit(app.exec_())
