from ryu.app.wsgi import ControllerBase, route
from custom.beta.tools.commodity_parser import commodity_parser as cm_parser
from webob import Response
from collections import defaultdict
import json

class TopologyRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(TopologyRestController, self).__init__(req, link, data, **config)
        self.topology_data = data['topology_data']
        self.controller = data['controller']
        self.group_db = data['multiGroup_data']

    @route('topology', '/topology', methods=['GET'])
    def get_topology(self, req, **kwargs):
        converted_data = self.topology_data.data_to_dict()
        body = json.dumps(converted_data, indent=4)
        return Response(content_type='application/json; charset=UTF-8', body=body)
    
    @route('server', '/multiGroupData', methods=['GET'])
    def get_multigroup_data(self, req, **kwargs):
        try:
            query = req.params.get('commodities')
            commodities = json.loads(query)  # 解 JSON 字串
        except Exception:
            return Response(status=400, body="Invalid query string")

        response_data = []
        for commodity in commodities:
            response_data.append(self.group_db.get_commodity_info(commodity))

        body = json.dumps(response_data, indent=4)
        return Response(content_type='application/json; charset=UTF-8', body=body)

        
    @route('server', '/add_commodity_request', methods=['POST'])
    def upload_commodities_data(self, req, **kwargs):
        try:
            body = req.body
            commodities = json.loads(body)

            print(f"Assign commodities to database")
            print(f"commodities: {commodities}")
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
            print(f"commodity name: {commodities_name}")

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
            # self.controller.ask_host_to_send_packets(commodities_name)
            self.controller.ask_host_to_send_packet_by_one_iperf(commodities_name)

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