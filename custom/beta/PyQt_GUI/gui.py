import sys, os
import json
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QTextEdit, QLabel, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from custom.beta.PyQt_GUI.rest_client import RestAPIClient

RYU_API_URL = "http://localhost:8080"
SSH_API_URL = "http://localhost:4888"

class RyuFlowMonitor(QWidget):

    def __init__(self):
        super().__init__()
        self.client = RestAPIClient(RYU_API_URL)
        self.client.set_ssh_url(SSH_API_URL)
        self.initUI()
        self.start_auto_fetch()
        self.connect_buttons()

    def initUI(self):
        self.setWindowTitle("Ryu Flow Table Monitor")
        self.setGeometry(100, 100, 1200, 700)

        # 主佈局
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        right_buttons_layout = QVBoxLayout()

        # Links 和 Hosts（橫向）
        links_hosts_layout = QHBoxLayout()
        self.links_text = QTextEdit()
        self.links_text.setReadOnly(True)
        self.links_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hosts_text = QTextEdit()
        self.hosts_text.setReadOnly(True)
        self.hosts_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        links_hosts_layout.addWidget(QLabel("Links"))
        links_hosts_layout.addWidget(self.links_text)
        links_hosts_layout.addWidget(QLabel("Hosts"))
        links_hosts_layout.addWidget(self.hosts_text)

        # Algorithm Result 區域
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addLayout(links_hosts_layout)
        left_layout.addWidget(QLabel("Algorithm Result"))
        left_layout.addWidget(self.result_text)

        # Record Result 區域
        self.record_result_text = QTextEdit()
        self.record_result_text.setReadOnly(True)
        self.record_result_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(QLabel("Record Result"))
        right_layout.addWidget(self.record_result_text)

        # 按鈕區域
        self.run_button = QPushButton("Run Algorithm")
        self.update_db_button = QPushButton("Update DB")
        self.set_host_switch_button = QPushButton("Set Host And Switch")
        self.start_send_packet_button = QPushButton("Start Send Packet")
        self.run_all_button = QPushButton("Run All Steps")
        self.clear_output_button = QPushButton("Clear Output")
        
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.update_db_button)
        right_buttons_layout.addWidget(self.set_host_switch_button)
        right_buttons_layout.addWidget(self.start_send_packet_button)
        right_buttons_layout.addWidget(self.run_all_button)
        right_buttons_layout.addWidget(self.clear_output_button)

        left_layout.addLayout(button_layout)
        right_layout.addLayout(right_buttons_layout)

        # 整合左右佈局
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 1)
        self.setLayout(main_layout)
    
    def start_auto_fetch(self):
        self.client.fetch_topology_data(self.links_text, self.hosts_text)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.client.fetch_topology_data(self.links_text, self.hosts_text))
        self.timer.start(15000)
    
    def connect_buttons(self):
        self.run_button.clicked.connect(lambda: self.client.run_algorithm_process(self.result_text))
        self.update_db_button.clicked.connect(lambda: self.client.upload_commodity_data(self.result_text, self.record_result_text))
        self.set_host_switch_button.clicked.connect(lambda: self.client.set_host_and_switch(self.record_result_text))
        self.start_send_packet_button.clicked.connect(lambda: self.client.send_packet(self.record_result_text))

        # self.run_all_button.clicked.connect(self.client.run_all_steps)
        # self.clear_output_button.clicked.connect(self.client.clear_all_texts)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RyuFlowMonitor()
    window.show()
    sys.exit(app.exec_())
