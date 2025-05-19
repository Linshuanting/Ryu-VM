import paramiko
import threading
import logging
import os
import json
from ipaddress import IPv6Address, IPv6Network
from flask import Flask, request, jsonify

# 設定 logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

app = Flask(__name__)
class SSHManager:
    def __init__(self):
        self.connection_infos = {}  # 儲存重連資訊
        self.default_host_nic = {}

    def add_host(self, hostname, ip, username, password=None, key_file=None):
        self.connection_infos[hostname] = {
            "hostname": hostname,
            "ip": ip,
            "username": username,
            "password": password,
            "key_file": key_file
        }
        logging.info(f"已儲存 {hostname} 的 SSH 連線資訊 ({ip})")

    def check_host(self, hostname):
        return hostname in self.connection_infos

    def _create_client(self, info):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if info.get("key_file"):
            client.connect(info["ip"], username=info["username"], key_filename=info["key_file"])
        else:
            client.connect(info["ip"], username=info["username"], password=info["password"])
        return client

    def execute_command(self, hostname, command):
        info = self.connection_infos.get(hostname)
        if not info:
            logging.error(f"無法執行 {hostname} 的指令，因為未提供 SSH 資訊")
            return None

        try:
            client = self._create_client(info)
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            client.close()

            if error:
                logging.warning(f"[{hostname}] 命令錯誤: {error}")
            return output if output else error
        except Exception as e:
            logging.error(f"執行指令時發生錯誤: {e}")
            return str(e)

    def upload_file(self, hostname, local_path, remote_path):
        info = self.connection_infos.get(hostname)
        if not info:
            return
        client = self._create_client(info)
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        client.close()
        logging.info(f"{local_path} 已上傳至 {hostname}:{remote_path}")

    def download_file(self, hostname, remote_path, local_path):
        info = self.connection_infos.get(hostname)
        if not info:
            return
        client = self._create_client(info)
        sftp = client.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        client.close()
        logging.info(f"{hostname}:{remote_path} 已下載至 {local_path}")

    def get_host_default_nic(self, hostname):

        if hostname in self.default_host_nic:
            return self.default_host_nic[hostname]

        logging.info(f"取得 {hostname} 的預設網卡")
        output = self.execute_command(hostname, "ip -br a")
        if not output:
            return None
        for line in output.split("\n"):
            parts = line.split()
            if len(parts) > 1 and "UP" in parts[1]:
                nic_name = parts[0].split('@')[0]
                logging.info(f"✅ {hostname} 的 Default NIC: {nic_name}")
                self.default_host_nic[hostname] = nic_name
                return nic_name
        logging.warning(f"⚠ {hostname} 無法獲取 Default NIC")
        return None

    def get_setting_route_ipv6_cmd(self, ip: str, host_nic: str) -> str:
        try:
            ipv6_addr = IPv6Address(ip)
            routing_ip = str(IPv6Network(f"{ipv6_addr}/16", strict=False).network_address)
            return f"ip -6 route add {routing_ip}/16 dev {host_nic}"
        except ValueError:
            logging.error(f"無效的 IPv6 地址: {ip}")
            return ""

    def get_setting_route_ipv6_del_cmd(self, ip: str, host_nic: str) -> str:
        try:
            ipv6_addr = IPv6Address(ip)
            routing_ip = str(IPv6Network(f"{ipv6_addr}/16", strict=False).network_address)
            return f"ip -6 route del {routing_ip}/16 dev {host_nic}"
        except ValueError:
            logging.error(f"無效的 IPv6 地址: {ip}")
            return ""

    def get_setting_ipaddr_ipv6_group_cmd(self, ip: str, host_nic: str) -> str:
        return f"ip addr add {ip} dev {host_nic} autojoin"

    def get_setting_ipaddr_ipv6_group_del_cmd(self, ip: str, host_nic: str) -> str:
        return f"ip addr del {ip} dev {host_nic}"

    def get_setting_maddr_ipv6_cmd(self, ip: str, host_nic: str) -> str:
        return f"ip -6 maddr add {ip} dev {host_nic}"

    def get_setting_maddr_ipv6_del_cmd(self, ip: str, host_nic: str) -> str:
        return f"ip -6 maddr del {ip} dev {host_nic}"

    def get_send_flabel_packet_cmd(self, script_path='/home/user/mininet/custom/flow_flabel.py', src_ip=None, dst_ip=None, fl_number_start=0x11000) -> str:
        return f"python {script_path} --src_ip {src_ip} --dst_ip {dst_ip} --fl_number_start {fl_number_start}"

    def get_send_flabel_packet_in_background_cmd(self, script_path='/home/user/mininet/custom/flow_flabel_background.py', src_ip=None, dst_ip=None, fl_number_start=0x11000) -> str:
        script_dir = os.path.dirname(script_path)
        return f"cd {script_dir} && setsid nohup python {script_path} --src_ip {src_ip} --dst_ip {dst_ip} --fl_number_start {fl_number_start} --daemon > /dev/null 2>&1 &"

    def get_iperf_setting_multicast_receiver_cmd(self, host, ip="ff38::1", port=6001, duration=10, script_path='/home/user/mininet/custom/simulation_result/raw_data/'):
        return f"setsid timeout {duration} iperf -s -u -e -V -B {ip} -p {port} -i 1 > {script_path}iperf_{ip.replace(':', '_')}_{host}_{port}.log 2>&1 &"

    def get_iperf_send_packet_cmd(self, ipv6, bw=10, time=10, port=5001):
        return f"setsid iperf -c {ipv6} -u -V -b {bw}M -t {time} -p {port} > /dev/null 2>&1 &"
    
    def get_update_table_of_modify_flabel_cmd(self, ipv6, dport, script_path="/home/user/mininet/custom/update_table.py"):
        return f"python {script_path} --ip {ipv6} --dport {dport}"

    def get_update_table_of_modify_flabel_one_iperf_cmd(self, ipv6, dport, weights, script_path="/home/user/mininet/custom/update_table_one_iperf.py"):
        weights_str = ",".join(map(str, weights))
        return f"python {script_path} --ip {ipv6} --dport {dport} --weights {weights_str}"

    def get_start_tcpdump_to_pcap_cmd(self, host, ipv6, nic, port, duration=10, script_path="/home/user/mininet/custom/"):
        pcap_filename = f"pcap/{ipv6}_{host}.pcap"
        return f"setsid timeout {duration} tcpdump -i {nic} udp port {port} -w {script_path}{pcap_filename} > /dev/null 2>&1 &"
    
    def get_analysis_pcap_cmd(self, host, ipv6, wait=10, script_path="/home/user/mininet/custom/"):
        pcap_filename = f"pcap/{ipv6}_{host}.pcap"
        output_filename = f"{ipv6}_{host}.csv"
        return f"setsid python {script_path}analysis_iperf_per_second.py --pcap {script_path}{pcap_filename} --wait {wait} --output {output_filename} --ssh > /dev/null 2>&1 &"

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

@app.route("/execute_del_ipv6_command", methods=["POST"])
def api_execute_del_ipv6_command():
    data = request.json
    host_nic = ssh_manager.get_host_default_nic(data["hostname"])
    del_cmd = ssh_manager.get_setting_ipaddr_ipv6_group_del_cmd(data["ip"], host_nic)
    result = ssh_manager.execute_command(data["hostname"], del_cmd)
    return jsonify({"output": result})

@app.route("/execute_del_route_command", methods=["POST"])
def api_execute_del_route_command():
    data = request.json
    host_nic = ssh_manager.get_host_default_nic(data["hostname"])
    del_cmd = ssh_manager.get_setting_route_ipv6_del_cmd(data["ip"], host_nic)
    result = ssh_manager.execute_command(data["hostname"], del_cmd)
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

@app.route("/execute_update_table_of_one_iperf_command", methods=["POST"])
def api_execute_update_modify_flabel_table_of_one_iperf_command():
    data = request.json
    cmd = ssh_manager.get_update_table_of_modify_flabel_one_iperf_cmd(
        ipv6 = data["dst"],
        dport=data["dport"],
        weights=data["weights"]
    )
    result = ssh_manager.execute_command(data["hostname"], cmd)
    return jsonify({"output": result})

@app.route("/execute_update_table_command", methods=["POST"])
def api_execute_update_modify_flabel_table_command():
    data = request.json
    cmd = ssh_manager.get_update_table_of_modify_flabel_cmd(
        ipv6 = data["dst"],
        dport=data["dport"]
    )
    result = ssh_manager.execute_command(data["hostname"], cmd)
    return jsonify({"output": result})

@app.route("/execute_iperf_server_command", methods=["POST"])
def api_execute_iperf_server_command():
    data = request.json
    for host in data["hostname"]:
        cmd = ssh_manager.get_iperf_setting_multicast_receiver_cmd(
            host=host,
            ip=data["dst"],
            port=data["port"],
            duration=data.get("time", 10)
        )
        result = ssh_manager.execute_command(host, cmd)
    return jsonify({"output": result})

@app.route("/execute_iperf_client_command", methods=["POST"])
def api_execute_iperf_client_command():
    data = request.json
    cmd = ssh_manager.get_iperf_send_packet_cmd(
        ipv6=data["dst"],
        bw=data["bw"],
        time=data["time"],
        port=data["port"]
    )
    result = ssh_manager.execute_command(data["hostname"], cmd)
    return jsonify({"output": result})

@app.route("/execute_nftable_add_rule_command", methods=["POST"])
def api_execute_nftable_add_rule_command():
    data = request.json

    hostname = data["hostname"]
    table = data.get("table", "myfilter")
    chain = data.get("chain", "prerouting")
    queue_num = data.get("queue", 2)

    # 支援單個 port 或多個 port
    ports = data.get("ports")
    port = data.get("port")

    if ports:
        # 多個 port
        port_expr = ", ".join(str(p) for p in ports)
        port_match = f"udp dport {{ {port_expr} }}"
    elif port:
        # 單個 port
        port_match = f"udp dport {port}"
    else:
        return jsonify({"error": "Missing 'port' or 'ports' in request"}), 400

    # 建立 nftables 規則，將指定 port 的 UDP 封包送入 NFQUEUE
    add_cmd = (
        f"nft add rule ip6 {table} {chain} {port_match} queue num {queue_num}"
    )

    result = ssh_manager.execute_command(hostname, add_cmd)
    return jsonify({
        "command": add_cmd,
        "output": result
    })

@app.route("/execute_send_mapping_to_socket", methods=["POST"])
def api_send_mapping_to_socket():
    data = request.json

    hostname = data["hostname"]
    ip = data["ip"]
    fl_p_dict = data["fl_p_dict"]
    script_path = "/home/user/mininet/custom/update_table_server_port.py"

    if not isinstance(fl_p_dict, dict):
        return jsonify({"error": "'fl_p_dict' must be a dict"}), 400

    # 將 fl_p_list 轉成合法 JSON 字串
    json_mapping_str = json.dumps(fl_p_dict)

    # 組出遠端執行指令
    cmd = f"python3 {script_path} --ip {ip} --mapping '{json_mapping_str}'"

    # 執行 SSH 指令
    result = ssh_manager.execute_command(hostname, cmd)

    return jsonify({
        "hostname": hostname,
        "command": cmd,
        "output": result
    })


@app.route("/execute_tcpdump_and_get_csv_command", methods=["POST"])
def api_execute_tcpdump_receiver_and_send_csv():
    data = request.json
    time = data["time"] + 5
    hosts = data["hostname"]
    results = []

    for host in hosts:
        result = []
        cmd = ssh_manager.get_start_tcpdump_to_pcap_cmd(
            host=host,
            ipv6=data["dst_ip"],
            nic=ssh_manager.get_host_default_nic(host),
            port=data["dport"],
            duration=time
        )
        res = ssh_manager.execute_command(host, cmd)
        result.append(res)

        cmd = ssh_manager.get_analysis_pcap_cmd(
            host=host,
            ipv6=data["dst_ip"],
            wait=time
        )
        res = ssh_manager.execute_command(host, cmd)
        result.append(res)

        results.append(result)
    
    return jsonify({"output": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4888)