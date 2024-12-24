import requests
import json

class RestAPIClient:
    def __init__(self, url):
        self.url = url

    def fetch_json_data(self):
        """
        从指定的 REST API URL 获取 JSON 数据。
        """
        try:
            response = requests.get(self.url)
            response.raise_for_status()  # 检查是否请求成功
            return response.json()       # 返回解析后的 JSON 数据
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from API: {e}")
            return None
