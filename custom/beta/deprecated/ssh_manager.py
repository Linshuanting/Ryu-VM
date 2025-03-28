import paramiko
import sqlite3
import threading
import logging
from flask import Flask, request, jsonify

# 設定 logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# 初始化 Flask API
app = Flask(__name__)

class SSHManager:
    def __init__(self, db_path="ssh_connections.db"):
        """初始化 SSH 管理器，並讀取已儲存的 SSH 連線"""
        self.clients = {}
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化 SQLite 資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ssh_connections (
            hostname TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT,
            key_file TEXT
        )
        """)
        conn.commit()
        conn.close()

    def load_connections(self):
        """從資料庫載入 SSH 連線"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, ip, username, password, key_file FROM ssh_connections")
        for hostname, ip, username, password, key_file in cursor.fetchall():
            self.add_host(hostname, ip, username, password, key_file)
        conn.close()

    def add_host(self, hostname, ip, username, password=None, key_file=None):
        """新增 SSH 連線，並存入資料庫"""
        if hostname in self.clients:
            logging.info(f"{hostname} 已經連線")
            return

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if key_file:
                client.connect(ip, username=username, key_filename=key_file)
            else:
                client.connect(ip, username=username, password=password)

            self.clients[hostname] = client
            logging.info(f"已連接到 {hostname} ({ip})")

            # 將資訊存入資料庫
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO ssh_connections (hostname, ip, username, password, key_file) 
            VALUES (?, ?, ?, ?, ?)""", (hostname, ip, username, password, key_file))
            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"連接 {hostname} ({ip}) 失敗: {e}")

    def execute_command(self, hostname, command):
        """執行遠端 SSH 指令"""
        if hostname not in self.clients:
            return f"錯誤: {hostname} 尚未連線"

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
            return f"錯誤: {hostname} 尚未連線"

        sftp = self.clients[hostname].open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        return f"{local_path} 已上傳至 {hostname}:{remote_path}"

    def download_file(self, hostname, remote_path, local_path):
        """下載檔案從遠端主機"""
        if hostname not in self.clients:
            return f"錯誤: {hostname} 尚未連線"

        sftp = self.clients[hostname].open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        return f"{hostname}:{remote_path} 已下載至 {local_path}"

    def close_all(self):
        """關閉所有 SSH 連線"""
        for host, client in self.clients.items():
            client.close()
            logging.info(f"已關閉 {host} 的 SSH 連線")

# 初始化 SSH 管理器
ssh_manager = SSHManager()
ssh_manager.load_connections()

# === Flask API ===

@app.route("/add_host", methods=["POST"])
def api_add_host():
    data = request.json
    ssh_manager.add_host(data["hostname"], data["ip"], data["username"], data.get("password"), data.get("key_file"))
    return jsonify({"message": f"{data['hostname']} 已新增"})

@app.route("/execute_command", methods=["POST"])
def api_execute_command():
    data = request.json
    result = ssh_manager.execute_command(data["hostname"], data["command"])
    return jsonify({"output": result})

@app.route("/upload_file", methods=["POST"])
def api_upload_file():
    data = request.json
    result = ssh_manager.upload_file(data["hostname"], data["local_path"], data["remote_path"])
    return jsonify({"message": result})

@app.route("/download_file", methods=["POST"])
def api_download_file():
    data = request.json
    result = ssh_manager.download_file(data["hostname"], data["remote_path"], data["local_path"])
    return jsonify({"message": result})

# 啟動 Flask 伺服器
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
