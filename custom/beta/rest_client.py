import requests
import json
from tools.utils import tuple_key_to_str
class RestAPIClient:
    def __init__(self, url):
        self.url = url

    def fetch_json_data(self):
        """
        從指定的 REST API URL 取得 JSON 資料。
        """
        try:
            response = requests.get(self.url + "/topology")
            response.raise_for_status()  # 檢查是否成功請求
            return response.json()       # 返回 JSON 資料
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from API: {e}")
            return None
    
    def post_json_data(self, data):
        """
        將 data (Python dict) 轉為 JSON 後，POST 到 self.url，
        回傳伺服器的 JSON 回應（若無回傳 JSON，可視需求調整）。
        """
        json_data = json.dumps(tuple_key_to_str(data), indent=4)
        print(json_data)
        try:
            response = requests.post(self.url + "/upload_algorithm_result", data=json_data)
            response.raise_for_status()  # 若非 2xx，拋出異常
            return response.text       # 假設伺服器也回傳 JSON
        except requests.exceptions.RequestException as e:
            print(f"Error posting data to API: {e}")
            return None
 
    
