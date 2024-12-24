from ryu.app.wsgi import ControllerBase, route
from webob import Response
from collections import defaultdict
import json

class TopologyRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(TopologyRestController, self).__init__(req, link, data, **config)
        self.topology_data = data['topology_data']

    @route('topology', '/topology', methods=['GET'])
    def get_topology(self, req, **kwargs):
        converted_data = self.topology_data.to_dict()
        body = json.dumps(converted_data, indent=4)
        return Response(content_type='application/json; charset=UTF-8', body=body)
    

    def defaultdict_to_dict(self, d):
        if isinstance(d, defaultdict):
            d = {k: self.defaultdict_to_dict(v) for k, v in d.items()}
        return d

