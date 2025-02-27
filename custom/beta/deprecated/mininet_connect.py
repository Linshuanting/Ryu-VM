import paramiko
from ipaddress import IPv6Address, IPv6Network


class MininetSSHManager:

    MULTI_GROUP_IP_STARTWITH = 'ff38'

    def __init__(self, hosts=None, username="root", password="root"):
        """
        初始化 Mininet SSH Manager
        :param hosts: 字典 { "h1": "192.168.56.101", "h2": "192.168.56.102" }
        :param username: SSH 登入使用者名稱
        :param password: SSH 密碼
        """
        if hosts is None:
            hosts = {}
        
        if not isinstance(hosts, dict):
            raise TypeError("hosts 參數必須是字典類型")
        
        if not isinstance(username, str) or not isinstance(password, str):
            raise TypeError("username 和 password 必須是字串")

        self.hosts = hosts
        self.username = username
        self.password = password

    def run_command(self, host, command):
        """
        在指定的 Mininet Host 上執行指令
        :param host: 主機名稱 (如 "h1")
        :param command: 需要執行的 shell 指令
        :return: 指令輸出的字串
        """
        if host not in self.hosts:
            return f"錯誤: 找不到主機 {host}"

        ip = self.hosts[host]
        print(f"[{host}] 連線到 {ip} 並執行指令: {command}")

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=self.username, password=self.password)

            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()

            ssh.close()

            if error:
                return f"[{host}] 錯誤: {error}"
            return f"[{host}] 成功: {output.strip()}"
        except Exception as e:
            return f"[{host}] SSH 連線失敗: {str(e)}"

    def batch_run_command(self, command):
        """
        在所有 Mininet Host 上執行相同指令
        :param command: 需要執行的 shell 指令
        :return: 所有主機的執行結果
        """
        results = {}
        for host in self.hosts:
            results[host] = self.run_command(host, command)
        return results

    def setup_ipv6_multicast(self):
        """
        在所有 Mininet Host 上設定 IPv6 多播路由
        """
        print("\n=== 設定所有 Mininet Host 的 IPv6 多播路由 ===")
        command = "ip -6 route add ff38::/16 dev h1-eth0 && ip -6 maddr add ff38::1 dev h1-eth0"
        results = self.batch_run_command(command)

        for host, result in results.items():
            print(result)

    def set_host(self, host, ip):
        if host in self.hosts:
            return f"已經有 {host}，其對應 ip {self.hosts[host]}"
        
        self.hosts[host] = ip
    
    def set_hosts(self, hosts:dict):
        for host, ip in hosts.items():
            self.set_host(host, ip)

    def get_host_NIC(self, host) -> str:
        return f"{host}-eth0"
    
    def run_source_cmd(self, host, group_ip):
        
        print(f"執行連線到 Source Host:{host} 指令")
        
        host_nic = self.get_host_NIC(host)
        route_cmd = self.get_setting_route_ipv6_cmd(host_nic, group_ip)
        # maddr_cmd = self.get_setting_maddr_ipv6_cmd(host_nic, group_ip)

        # cmd = f"{route_cmd} && {maddr_cmd}"
        # print(self.run_command(host, cmd))

        print(f"route_cmd: {self.run_command(host, route_cmd)}")
        # print(f"maddr_cmd: {self.run_command(host, maddr_cmd)}")

    def run_destinations_cmd(self, hosts, group_ip):

        for host in hosts:
            print(f"執行連線到 Destination Host:{host} 指令")

            host_nic = self.get_host_NIC(host)
            ipaddr_cmd = self.get_setting_ipaddr_ipv6_group_cmd(host_nic, group_ip)
            # maddr_cmd = self.get_setting_maddr_ipv6_cmd(host_nic, group_ip)

            # cmd = f"{ipaddr_cmd} && {maddr_cmd}"
            # print(self.run_command(host, cmd))

            print(f"ipaddr_cmd: {self.run_command(host, ipaddr_cmd)}")

    def run_sending_flabel_packet_cmd(self, host, src_ip, dst_ip, flabel_start):

        print(f"執行連線到 Host:{host}，並進行 send flabel packet 指令")

        cmd = self.get_send_flabel_cmd(src=src_ip, dst=dst_ip, fl_number_start=flabel_start)
        print(self.run_command(host, cmd))

    def get_setting_route_ipv6_cmd(self, host_NIC: str, ip: str) -> str:
        """
        根據 IPv6 地址獲取適合的路由命令
        :param host_NIC: 目標網卡名稱
        :param ip: 來源 IPv6 地址
        :return: `ip -6 route add` 的 Shell 指令
        """
        try:
            # 解析 IPv6 並獲取前 16-bit（/16 網段）
            ipv6_addr = IPv6Address(ip)
            routing_ip = str(IPv6Network(f"{ipv6_addr}/16", strict=False).network_address)
            # routing_ip = str(ipv6_addr)

            # 構造 `ip -6 route add` 指令
            route_cmd = f"ip -6 route add {routing_ip}/16 dev {host_NIC}"
            # route_cmd = f"ip -6 route add {routing_ip} dev {host_NIC}"
            
            return route_cmd
        except ValueError:
            raise ValueError(f"無效的 IPv6 地址: {ip}")
    
    def get_setting_ipaddr_ipv6_group_cmd(self, host_NIC, ip) -> str:
        ipaddr_cmd = f"ip addr add {ip} dev {host_NIC} autojoin"
        return ipaddr_cmd
    
    def get_setting_maddr_ipv6_cmd(self, host_NIC, ip) -> str:
        maddr_cmd = f"ip -6 maddr add {ip} dev {host_NIC}"
        return maddr_cmd
    
    def get_send_flabel_cmd(self, dir='/home/user/mininet/custom/flow_flabel.py', src=None, dst=None, fl_number_start=0x11000):
        cmd = f"python {dir} --src_ip {src} --dst_ip {dst} --fl_number_start {fl_number_start}"
        return cmd
    
    def print_hosts(self):
        print("打印 mininet connect 的 hosts 內存下了甚麼")
        for host, ip in self.hosts.items():
            print(f"host:{host}, ip:{ip}")
