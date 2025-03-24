import paramiko
import threading
import logging
import os
from ipaddress import IPv6Address, IPv6Network
from flask import Flask, request, jsonify

# 設定 logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

app = Flask(__name__)
class SSHManager:
    def __init__(self):
        """初始化 SSH 管理器，存儲所有的 SSH 連線"""
        self.clients = {}

    def add_host(self, hostname, ip, username, password=None, key_file=None):
        """
        新增 SSH 連線
        :param hostname: 目標主機 Hostname
        :param ip: 目標主機 IP 
        :param username: SSH 使用者名稱
        :param password: SSH 密碼（可選）
        :param key_file: SSH 私鑰（可選）
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自動接受未知的 SSH Key

        try:
            if key_file:
                client.connect(ip, username=username, key_filename=key_file)
            else:
                client.connect(ip, username=username, password=password)

            self.clients[hostname] = client
            logging.info(f"已連接到 {hostname} ({ip})")
        except Exception as e:
            logging.error(f"連接 {hostname} ({ip}) 失敗: {e}")

    def check_host(self, hostname):
        if hostname in self.clients:
            return self.clients[hostname]
        return None
    
    def execute_command(self, hostname, command):
        """
        在指定主機上執行指令
        :param hostname: 目標主機
        :param command: 要執行的指令
        :return: 指令輸出的結果
        """
        if hostname not in self.clients:
            logging.error(f"{hostname} 尚未連接")
            return None

        client = self.clients[hostname]
        stdin, stdout, stderr = client.exec_command(command)

        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        if error:
            logging.warning(f"[{hostname}] 命令錯誤: {error}")
        return output if output else error

    def upload_file(self, hostname, local_path, remote_path):
        """上傳檔案到遠端主機"""
        if hostname not in self.clients:
            logging.error(f"{hostname} 尚未連接")
            return

        sftp = self.clients[hostname].open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        logging.info(f"{local_path} 已上傳至 {hostname}:{remote_path}")

    def download_file(self, hostname, remote_path, local_path):
        """下載檔案從遠端主機"""
        if hostname not in self.clients:
            logging.error(f"{hostname} 尚未連接")
            return

        sftp = self.clients[hostname].open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        logging.info(f"{hostname}:{remote_path} 已下載至 {local_path}")

    def get_host_default_nic(self, hostname):

        """
        獲取指定 Host 的 Default NIC (主要網卡名稱)
        """
        if hostname not in self.clients:
            logging.error(f"❌ {hostname} 尚未連接")
            return None

        output = self.execute_command(hostname, "ip -br a")
        if not output:
            return None

        for line in output.split("\n"):
            parts = line.split()
            if len(parts) > 1 and "UP" in parts[1]:  # 過濾出 "UP" 狀態的網卡
                nic_name = parts[0].split('@')[0]
                logging.info(f"✅ {hostname} 的 Default NIC: {nic_name}")
                return nic_name

        logging.warning(f"⚠ {hostname} 無法獲取 Default NIC")
        return None

    def execute_parallel(self, command):
        """在所有已連接的主機上 **並行** 執行指令"""
        def run_command(host):
            output = self.execute_command(host, command)
            logging.info(f"[{host}] {output}")

        threads = []
        for host in self.clients.keys():
            thread = threading.Thread(target=run_command, args=(host,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()  # 等待所有執行緒完成

    def execute_parallel_for_host_list(self, hosts_list, command):
        """在指定的主機上 **並行** 執行指令"""
        def run_command(host):
            output = self.execute_command(host, command)
            logging.info(f"[{host}] {output}")

        threads = []
        for host in hosts_list:
            thread = threading.Thread(target=run_command, args=(host,))
            threads.append(thread)
            thread.start()

        # 等待所有執行緒完成
        for thread in threads:
            thread.join()

    def close_all(self):
        """關閉所有 SSH 連線"""
        for host, client in self.clients.items():
            client.close()
            logging.info(f"已關閉 {host} 的 SSH 連線")

    def get_setting_route_ipv6_cmd(self, ip: str, host_nic: str) -> str:
        """取得設定 IPv6 路由的指令"""
        try:
            ipv6_addr = IPv6Address(ip)
            routing_ip = str(IPv6Network(f"{ipv6_addr}/16", strict=False).network_address)
            route_cmd = f"ip -6 route add {routing_ip}/16 dev {host_nic}"
            return route_cmd
        except ValueError:
            logging.error(f"無效的 IPv6 地址: {ip}")
            return ""

    def get_setting_ipaddr_ipv6_group_cmd(self, ip: str, host_nic: str) -> str:
        """取得設定 IPv6 地址組的指令"""
        return f"ip addr add {ip} dev {host_nic} autojoin"

    def get_setting_maddr_ipv6_cmd(self, ip: str, host_nic: str) -> str:
        """取得設定 IPv6 多播地址的指令"""
        return f"ip -6 maddr add {ip} dev {host_nic}"

    def get_send_flabel_packet_cmd(self, script_path='/home/user/mininet/custom/flow_flabel.py',
                            src_ip=None, dst_ip=None, fl_number_start=0x11000) -> str:
        """取得發送 FLabel 流量的指令"""
        return f"python {script_path} --src_ip {src_ip} --dst_ip {dst_ip} --fl_number_start {fl_number_start}"
    
    def get_send_flabel_packet_in_background_cmd(self, script_path='/home/user/mininet/custom/flow_flabel_background.py',
                            src_ip=None, dst_ip=None, fl_number_start=0x11000) -> str:
        
        script_dir = os.path.dirname(script_path)

        return f"cd {script_dir} && setsid nohup python {script_path} --src_ip {src_ip} --dst_ip {dst_ip} --fl_number_start {fl_number_start} --daemon > /dev/null 2>&1 &"

    def get_iperf_setting_multicast_receiver_cmd(self, ip="ff38::1"):
        iperf3 = f"iperf3 -s -p 5201 &"
        iperf = f"setsid iperf -s -u -V -B {ip} -p 5201 > /dev/null 2>&1 &"
        return iperf
    
    def get_iperf_send_packet_cmd(self, ipv6, bw=10, time=5, port = 5001):
        """取得發送 iperf udp 流量的指令"""
        iperf3 = f"iperf3 -c {ipv6} -u -b {bw}M -t {time} -p 5201 -6"
        iperf = f"setsid iperf -c {ipv6} -u -V -b {bw}M -t {time} -p {port} > /dev/null 2>&1 &"
        return iperf
    
ssh_manager = SSHManager()

@app.route("/add_host", methods=["POST"])
def api_add_host():
    data = request.json
    ssh_manager.add_host(data["hostname"], data["ip"], data["username"], data.get("password"), data.get("key_file"))
    return jsonify({"message": f"{data['hostname']} 已新增"})

@app.route("/check_host", methods=["POST"])
def api_check_host():
    data = request.json
    result = ssh_manager.check_host(data["hostname"])
    return jsonify({"output": bool(result) if result is not None else None})

@app.route("/execute_command", methods=["POST"])
def api_execute_command():
    data = request.json
    result = ssh_manager.execute_command(data["hostname"], data["command"])
    return jsonify({"output": result})

@app.route("/get_host_nic", methods=["POST"])
def api_get_hostNIC():
    data = request.json
    host_nic = ssh_manager.get_host_default_nic(data["hostname"])
    return jsonify({"output": host_nic})

@app.route("/execute_set_ipv6_command", methods=["POST"])
def api_execute_set_ipv6_command():
    data = request.json
    host_nic = ssh_manager.get_host_default_nic(data["hostname"])
    ipaddr_cmd = ssh_manager.get_setting_ipaddr_ipv6_group_cmd(data["ip"], host_nic)
    
    result = ssh_manager.execute_command(data["hostname"], ipaddr_cmd)
    
    return jsonify({"output": result})

@app.route("/execute_set_route_command", methods=["POST"])
def api_execute_set_route_command():
    data = request.json
    host_nic = ssh_manager.get_host_default_nic(data["hostname"])
    route_cmd = ssh_manager.get_setting_route_ipv6_cmd(data["ip"], host_nic)

    result = ssh_manager.execute_command(data["hostname"], route_cmd)
    
    return jsonify({"output": result})

@app.route("/execute_send_packet_command", methods=["POST"])
def api_execute_send_packet_command():
    data = request.json
    cmd = ssh_manager.get_send_flabel_packet_in_background_cmd(
        src_ip=data["src"],
        dst_ip=data["dst"],
        fl_number_start=data["flabel"]
    )
    result = ssh_manager.execute_command(data["hostname"], cmd)
    return jsonify({"output": result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4888)