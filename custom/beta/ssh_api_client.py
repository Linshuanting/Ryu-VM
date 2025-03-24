import sys
import http.client
import json

class SSHManagerAPIWrapper:
    def __init__(self, host="localhost", port=4888):
        self.host = host
        self.port = port

    def _post(self, path, data):
        conn = http.client.HTTPConnection(self.host, self.port)
        headers = {'Content-type': 'application/json'}
        json_data = json.dumps(data)
        conn.request("POST", path, json_data, headers)
        response = conn.getresponse()
        if response.status != 200:
            print(f"[ERROR] HTTP {response.status} on {path}")
            return {}
        return json.loads(response.read().decode())

    def add_host(self, hostname, ip, username, password=None, key_file=None):
        return self._post("/add_host", {
            "hostname": hostname,
            "ip": ip,
            "username": username,
            "password": password,
            "key_file": key_file
        })

    def check_host(self, hostname):
        return self._post("/check_host", {
            "hostname": hostname
        }).get("output", False)

    def execute_command(self, hostname, command):
        return self._post("/execute_command", {
            "hostname": hostname,
            "command": command
        }).get("output", "")

    def get_host_default_nic(self, hostname):
        return self._post("/get_host_nic", {
            "hostname": hostname
        }).get("output", "")

    def execute_set_ipv6_command(self, hostname, ip):
        return self._post("/execute_set_ipv6_command", {
            "hostname": hostname,
            "ip": ip
        }).get("output", "")

    def execute_set_route_command(self, hostname, ip):
        return self._post("/execute_set_route_command", {
            "hostname": hostname,
            "ip": ip
        }).get("output", "")

    def execute_send_packet_command(self, hostname, src, dst, flabel):
        return self._post("/execute_send_packet_command", {
            "hostname": hostname,
            "src": src,
            "dst": dst,
            "flabel": flabel
        }).get("output", "")

    def execute_iperf_server_command(self, hostname, dst_ip, port):
        return self._post("/execute_iperf_server_command", {
            "hostname": hostname,
            "dst": dst_ip,
            "port": port
        }).get("output", "")

    def execute_iperf_client_command(self, hostname, dst_ip, bw, port, time=5):
        return self._post("/execute_iperf_client_command", {
            "hostname": hostname,
            "dst": dst_ip,
            "bw": bw,
            "time": time,
            "port": port
        }).get("output", "")
