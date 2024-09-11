import hashlib
import time

class LoopDetectionTable:
    def __init__(self, timeout=5):
        """
        初始化循環檢測表。
        :param timeout: 記錄在表中的封包將保持的時間（秒），超過這個時間後將被刪除。
        """
        self.table = {}
        self.timeout = timeout
    
    def _hash_packet(self, packet_data):
        """
        生成封包的哈希值以便存儲和檢查。
        :param packet: 封包數據
        :return: 封包的哈希值
        """
        # 確保 packet_data 是 bytes 類型
        if not isinstance(packet_data, bytes):
            packet_data = bytes(packet_data)  # 將封包數據轉換為 bytes 類型
        return hashlib.sha256(packet_data).hexdigest()


    def add_packet(self, packet):
        """
        將封包添加到檢測表。
        :param packet: 封包數據
        """
        packet_hash = self._hash_packet(packet)
        self.table[packet_hash] = time.time()

    def is_packet_duplicate(self, packet):
        """
        檢查封包是否已存在於檢測表中。
        :param packet: 封包數據
        :return: 如果封包存在且在 timeout 時間內，返回 True，否則返回 False
        """
        packet_hash = self._hash_packet(packet)
        current_time = time.time()
        if packet_hash in self.table:
            # 如果封包存在且在 timeout 時間內
            if current_time - self.table[packet_hash] <= self.timeout:
                return True
            else:
                # 超時，從表中刪除該封包
                del self.table[packet_hash]
        return False

    def clean_up(self):
        """
        清除超時的封包記錄。
        """
        current_time = time.time()
        expired_packets = [packet for packet, timestamp in self.table.items() if current_time - timestamp > self.timeout]
        for packet in expired_packets:
            del self.table[packet]
