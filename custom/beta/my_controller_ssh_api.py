import requests
import logging

class SSHManagerAPIWrapper:
    def __init__(self, base_url="http://localhost:4888"):
        self.base_url = base_url

    def add_host(self, hostname, ip, username, password=None, key_file=None):
        payload = {
            "hostname": hostname,
            "ip": ip,
            "username": username,
            "password": password,
            "key_file": key_file
        }
        r = requests.post(f"{self.base_url}/add_host", json=payload)
        return r.json()

    def check_host(self, hostname):
        r = requests.post(f"{self.base_url}/check_host", json={"hostname": hostname})
        return r.json().get("output", False)

    def execute_command(self, hostname, command):
        r = requests.post(f"{self.base_url}/execute_command", json={
            "hostname": hostname,
            "command": command
        })
        return r.json().get("output", "")

    def get_host_default_nic(self, hostname):
        r = requests.post(f"{self.base_url}/get_host_nic", json={"hostname": hostname})
        return r.json().get("output", "")

    def execute_set_ipv6_command(self, hostname, ip):
        r = requests.post(f"{self.base_url}/execute_set_ipv6_command", json={
            "hostname": hostname,
            "ip": ip
        })
        return r.json().get("output", "")

    def execute_set_route_command(self, hostname, ip):
        r = requests.post(f"{self.base_url}/execute_set_route_command", json={
            "hostname": hostname,
            "ip": ip
        })
        return r.json().get("output", "")

    def execute_send_packet_command(self, hostname, src, dst, flabel):
        r = requests.post(f"{self.base_url}/execute_send_packet_command", json={
            "hostname": hostname,
            "src": src,
            "dst": dst,
            "flabel": flabel
        })
        return r.json().get("output", "")
