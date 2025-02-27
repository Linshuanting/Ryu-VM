from ryu.app.wsgi import ControllerBase, route
from webob import Response
from collections import defaultdict
from beta.tools.commodity_parser import commodity_parser as cm_parser
import json

class TopologyRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(TopologyRestController, self).__init__(req, link, data, **config)
        self.topology_data = data['topology_data']
        self.controller = data['controller']

    @route('topology', '/topology', methods=['GET'])
    def get_topology(self, req, **kwargs):
        converted_data = self.topology_data.data_to_dict()
        body = json.dumps(converted_data, indent=4)
        return Response(content_type='application/json; charset=UTF-8', body=body)
    
    
    @route('server', '/upload_algorithm_result', methods=['POST'])
    def upload_data(self, req, **kwargs):
        """
        接收客户端发送的数据
        """
        try:
            # 从请求体中解析 JSON 数据
            body = req.body
            data = json.loads(body)
            print("Received data from client:")
            print(f"data type: {type(data)}")
            print(json.dumps(data, indent=4, ensure_ascii=False))

            self.topology_data.set_commodities_and_paths(data['commodities_and_paths'])
            self.controller.run(data['commodities_data'])
            # self.controller.test()
            

            # 返回响应
            return Response(status=200, body="Data received successfully")
        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")
        
    @route('server', '/send_algorithm_result_to_switch', methods=['POST'])
    def upload_data_to_db(self, req, **kwargs):
        try:
            # 从请求体中解析 JSON 数据
            body = req.body
            data = json.loads(body)
            print("Received data from client:")
            print(f"data type: {type(data)}")

        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")
        
    @route('server', '/add_commodity_request', methods=['POST'])
    def upload_commodities_data(self, req, **kwargs):
        try:
            body = req.body
            commodities = json.loads(body)

            print(f"Assign commodities to database")
            self.controller.assign_commodities_to_db(commodities)

        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")
    
    @route('server', '/update_host_and_switch_through_commodities', methods=['POST'])
    def upload_hosts_switches_data(self, req, **kwargs):
        try:
            body = req.body
            parser = cm_parser()
            commodities_name, _ = parser.parser(json.loads(body))

            print(f"Setting configuration to hosts and switches")
            self.controller.setting_commodity_ip_to_host(commodities_name)
            self.controller.apply_instruction_to_switch(commodities_name)

        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")
    
    @route('server', '/send_packet', methods=['POST'])
    def send_packets_from_host(self, req, **kwargs):
        try:
            body = req.body
            parser = cm_parser()
            commodities_name, _ = parser.parser(json.loads(body))

            print(f"Start sending packet ......")
            self.controller.ask_host_to_send_packets(commodities_name)

        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")
        
    @route('server', '/test', methods=['POST'])
    def test_function(self, req, **kwargs):
        """
        呼叫 `/test` 時執行某些操作，不回傳內容
        """
        try:
            # 執行你要的操作，例如記錄 log
            print("[INFO] test_function 被觸發，執行操作中...")

            # 這裡可以加入你要執行的邏輯，例如修改狀態、觸發事件
            body = req.body
            commodities = json.loads(body)
            print("Received data from client:")
            print(f"data type: {type(commodities)}")
            print(f"commodities: {commodities}")

            name_list = self.controller.assign_commodities_to_db(commodities)
            self.controller.setting_commodity_ip_to_host(name_list)
            self.controller.apply_instruction_to_switch(name_list)
            self.controller.ask_host_to_send_packets(name_list)

            # 回傳 HTTP 204 (No Content)，表示成功但沒有內容
            return Response(status=204)

        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"伺服器錯誤: {str(e)}")