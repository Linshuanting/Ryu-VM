from ryu.app.wsgi import ControllerBase, route
from webob import Response
from collections import defaultdict
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
            self.controller.assign_commodities_hosts_to_multi_ip(data['commodities_data'])
            self.controller.send_instruction()
            # self.controller.test()
            

            # 返回响应
            return Response(status=200, body="Data received successfully")
        except Exception as e:
            import traceback
            traceback.print_exc()  # 印出完整堆疊
            return Response(status=500, body=f"Error: {e}")

