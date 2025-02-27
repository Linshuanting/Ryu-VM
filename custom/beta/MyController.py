from topo_find import TopoFind
from typing import List, Dict, Tuple, Set
import tools.selection_method_parser as sm_parser
from ryu.lib.packet import ethernet, ether_types
from ryu.app.wsgi import WSGIApplication
from tools.utils import print_dict, append_to_json, initialize_file
from topo_rest_controller import TopologyRestController
from tools.topo_parser import TopologyParser
from data_structure.multiGroup_db import MultiGroupDB as MG_DB
from tools.commodity_parser import commodity_parser as cm_parser
from tools.ssh_connect import SSHManager

class MyController(TopoFind):

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)
        print("My Controller Initialize")
        self.group_id_counter = 1
        self.priority = 100
        self.group_db = MG_DB()
        self.sshd = SSHManager()
        self.file_name = "~/mininet/custom/output.json"
        initialize_file(self.file_name)
        self.start_wsgi(**kwargs)

    def test(self):
        # test function
        pass

    def apply_instruction_to_switch(self, name_list):

        self.logger.info(f"send {name_list} to switch")

        for name in name_list:
            commodity = self.group_db.get_commodity(name)
            commodity_group_list = self.group_db.get_commodity_group_list(name)
            src = self.group_db.get_src(name)
            dsts = self.group_db.get_dsts(name)
            paths = self.group_db.get_paths(name)

            for group in commodity_group_list:
                
                flow_inport_to_switch = {}
                flow_out_port = {}
                nodes = set()

                for (u, v), bw in group.get_path().items():
                    
                    port_u, port_v = self.topo.get_link(u, v)
                    flow_out_port.setdefault(u, []).append((port_u, bw))
                    flow_inport_to_switch[v] = port_v
                    
                    if not u.startswith('h'):
                        nodes.add(u)
                    if not v.startswith('h'):
                        nodes.add(v)

                ipv6_addr = group.get_ipv6()
                flabel = group.get_flabel()
                mask = group.get_flabel_mask()

                self.logger.info(f"multi ipv6:{ipv6_addr}, flabel:{hex(flabel)}, mask:{hex(mask)}")

                # node is datapath_id
                for node in nodes:
                    dp = self.topo.get_datapath(node)
                    out_port_list = flow_out_port[node]
                    inport = flow_inport_to_switch[node]
                    group_id = self.group_id_counter

                    if len(out_port_list) > 1:
                        self.send_group_multicast_method(dp, out_port_list, group_id)
                    else:
                        self.send_group_selection_method(dp, out_port_list, group_id)

                    
                        # self.send_flowMod_to_switch(dp, inport, group_id, multi_ip)
                    self.send_flowMod_to_switch(
                            dp, 
                            inport, 
                            group_id, 
                            multi_ip=ipv6_addr, 
                            multi_flabel_val=flabel, 
                            multi_flabel_mask=mask)
                    
                    self.group_id_counter+=1

    def set_ssh_connect_way(self, host):
        
        if self.sshd.check_host(host):
            return
        
        if not self.topo.get_host_single_ipv6(host):
            return
        
        self.logger.info(f"Add {host} in ssh database, ip: {self.topo.get_host_single_ipv6(host)}")

        self.sshd.add_host(
                hostname=host, 
                ip=self.topo.get_host_single_ipv6(host),
                username='root',
                password='root')
    
    def setting_commodity_ip_to_host(self, name_list):
        
        self.logger.info(f"Start setting commodity ip to host")

        for name in name_list:
            src = self.group_db.get_src(name)
            dsts = self.group_db.get_dsts(name)
            multi_group_ip = self.group_db.get_ipv6(name)

            self.logger.info(f"name:{name}, src:{src}, dsts:{dsts}, ip:{multi_group_ip}")

            nodes = [src] + dsts 

            self.logger.info(f"nodes: {nodes}")

            # 確認 sshd 裡面存入了連接方式
            # 若是沒有，則存入
            for node in nodes:
                self.set_ssh_connect_way(node)

                host_nic = self.sshd.get_host_default_nic(node)
                ipaddr_cmd = self.sshd.get_setting_ipaddr_ipv6_group_cmd(multi_group_ip, host_nic)
                maddr_cmd = self.sshd.get_setting_maddr_ipv6_cmd(multi_group_ip, host_nic)
                route_cmd = self.sshd.get_setting_route_ipv6_cmd(multi_group_ip, host_nic)

                self.sshd.execute_command(node, ipaddr_cmd)
                self.sshd.execute_command(node, route_cmd)
                self.sshd.execute_command(node, maddr_cmd)

    def ask_host_to_send_packets(self, commodities_name_list):
        
        for name in commodities_name_list:
            src = self.group_db.get_src(name)
            src_ip = self.topo.get_host_single_ipv6(src)
            group_multi_ip = self.group_db.get_ipv6(name)

            for group in self.group_db.get_commodity_group_list(name):
                flabel = group.get_flabel()
                cmd = self.sshd.get_send_flabel_packet_cmd(
                    src_ip=src_ip,
                    dst_ip=group_multi_ip,
                    fl_number_start=flabel
                )

                self.logger.info(f"** Start send flabel packet from {src}")

                self.sshd.execute_command(src, cmd)
    
    def send_flowMod_to_switch(self, 
                               datapath, 
                               inport, 
                               group_id, 
                               multi_ip=None, 
                               multi_flabel_val = None,
                               multi_flabel_mask = None):
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(
            in_port=inport,
            eth_type=ether_types.ETH_TYPE_IPV6,
            ipv6_dst=multi_ip,
            ipv6_flabel = (multi_flabel_val, multi_flabel_mask) # mask 後面 12 bits(3 bytes)，只看前 8 bits
        )
        actions = [parser.OFPActionGroup(group_id)]
        # actions = [parser.OFPActionOutput(1)] 
        self.add_flow(datapath, self.priority, match, actions)
    
    def send_group_multicast_method(self, datapath, port_weight_list, group_id):

        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        buckets = []
        bucket_id = 0

        for port, weight in port_weight_list:
            actions = [parser.OFPActionOutput(port)]
            bucket = parser.OFPBucket(
                actions=actions,
                bucket_id=bucket_id,
            )
            buckets.append(bucket)
            bucket_id+=1
        
        req = parser.OFPGroupMod(datapath=datapath, 
                                    command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_ALL, 
                                    group_id=group_id,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets
                                    )
        
        datapath.send_msg(req)

    def send_group_selection_method(self, datapath, port_weight_list, group_id):

        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        buckets = []
        bucket_id = 0

        selection_method = "hash"
        selection_method_param = 0

        for port, weight in port_weight_list:
            actions = [parser.OFPActionOutput(port)]
            properties = [parser.OFPGroupBucketPropWeight(type_= ofp.OFPGBPT_WEIGHT, weight=weight)]
            bucket = parser.OFPBucket(
                actions=actions,
                bucket_id=bucket_id,
                properties = properties
            )
            buckets.append(bucket)
            bucket_id+=1
        
        property = sm_parser.OFPGroupPropExperimenter(
            type_=ofp.OFPGPT_EXPERIMENTER,
            selection_method=selection_method,
            selection_method_param = selection_method_param,
            ipv6_flabel=sm_parser.OFP_GROUP_PROP_FIELD_MATCH_ALL_IPV6_FLABEL
        )
        properties = [property]
        req = parser.OFPGroupMod(datapath=datapath, 
                                    command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_SELECT, 
                                    group_id=group_id,
                                    # command_bucket_id=command_bucket_id, 
                                    buckets=buckets,
                                    properties=properties
                                    )
        
        datapath.send_msg(req)

    def assign_commodities_to_db(self, commodities) -> List:
        
        parser = cm_parser()
        names, commodities_dict = parser.parser(commodities)

        self.logger.info(f"Start writting commodities to database in RYU")

        for name in names:
            src = parser.parse_src(name, commodities_dict)
            dsts = parser.parse_dsts(name, commodities_dict)
            paths = parser.parse_paths(name, commodities_dict)
            bw = parser.parse_demand(name, commodities_dict)
            self.group_db.set_commodities(
                commodtiy_name=name,
                src=src,
                dsts=dsts,
                paths=paths,
                bw=bw
            )
        
        return names
            
    def record_data_to_json(self, commodity, multi_ip, src, dsts, multi_flabel_val, multi_flabel_mask, tree_bandwidth):
        """
        組織資料並記錄到 JSON 檔案。
        """
        # 組織要儲存的資料
        data = {
            "commodity": commodity,
            "multi_ip": multi_ip,
            "src": src,
            "dsts": dsts,
            "multi_flabel_val": f"{multi_flabel_val:05x}",
            "multi_flabel_mask": f"{multi_flabel_mask:05x}",
            "tree_bandwidth": tree_bandwidth
        }
        
        # 呼叫函式儲存資料
        append_to_json(self.file_name, data)
    
    def start_wsgi(self, **kwargs):
        print("Initializing WSGI service...")
        wsgi = kwargs.get('wsgi')
        if wsgi:
            print("WSGI object loaded successfully.")
            wsgi.register(TopologyRestController, {
                'topology_data': self.topo,
                'controller': self
                })
            print("TopologyController registered.")
        else:
            print("Error: WSGIApplication is not loaded.")