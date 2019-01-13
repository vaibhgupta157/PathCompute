import os, re, time, sys
import requests

from odl_details import *
from binascii import unhexlify, b2a_base64
import jinja2
import struct
import base64
import json
import logging
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter

logging.basicConfig(filename='logs/odl_bgp.log',level=logging.INFO)

# Function for GET request
def get_url(url):
      '''request url'''
      headers = {'Content-type': 'application/json'}
      try:
            response =  requests.get(url, headers = headers, auth = (ODL_USER, ODL_PASS), verify=False)
            logging.info("Url get Status: %s" % response.status_code)
            if response.status_code in [200]:
                  return response.json()
            else:
                  logging.info(str(response.text))
                  return "Error from ODL or incorrect API call" 
      except requests.exceptions.ConnectionError, e:
            logging.error('Connection Error: %s' % e.message)
            return "Not able to fetch data from ODL" 

# Function for POST request
def post_url(url, data):
      headers = {'Content-type': 'application/xml'}
      try:
            response =  requests.post(url, data = data, headers = headers, auth = (ODL_USER, ODL_PASS), verify=False)
            if response.status_code in [200, 204] and (not response.text or 'error' not in str(response.text)):
                  return "successfully configured" 
            else:
                  logging.info(str(response.text))
                  return "Error from ODL or incorrect API call"
      except requests.exceptions.ConnectionError, e:
            logging.error('Connection Error: %s' % e.message)
            return "Unable to push configuration to ODL" 

# Function for DELETE request
def delete_url(url, data):
      headers = {'Content-type': 'application/xml'} 
      try:
            response =  requests.delete(url, data = data, headers = headers, auth = (ODL_USER, ODL_PASS), verify=False)
            if response.status_code in [200, 204] and (not response.text or 'error' not in str(response.text)):
                  return "successfully deleted" 
            else:
                  logging.info(str(response.text))
                  return "Error from ODL or incorrect API call"
      except requests.exceptions.ConnectionError, e:
            logging.error('Connection Error: %s' % e.message)
            return "Unable to delete configuration from ODL" 

#Define node class
class nodes(object):
      def __init__(self, node_id, router_id, prefixes, pcc):
            self.node_id = node_id
            self.router_id = router_id
            self.prefixes = prefixes
            self.pcc = pcc

#Define link class
class links(object):
      def __init__(self, src_node_id, dest_node_id, src_ip, dest_ip, nw_type, ted, phy_bw, color, resv_bw, unresv_bw, igp_cost, ted_cost):
            self.src_node_id = src_node_id
            self.dest_node_id = dest_node_id
            self.src_ip = src_ip
            self.dest_ip = dest_ip
            self.nw_type = nw_type
            self.ted = ted
            self.phy_bw = phy_bw
            self.color = color
            self.resv_bw = resv_bw
            self.unresv_bw = unresv_bw 
            self.igp_cost = igp_cost
            self.ted_cost = ted_cost

#convert decimal bandwidth in bps to base64 for LSP pushing
def base64encode(bw_bps):
      hex_rep = hex(struct.unpack('<I', struct.pack('<f', bw_bps/8))[0]).lstrip('0x')
      return b2a_base64(unhexlify(hex_rep)) 

#convert base64 to decimal bandwidth in bps
def base64decode(base_64):
      hex_rep =  base64.b64decode(base_64).encode('hex')
      bw_Bps = struct.unpack('>f', unhexlify(hex_rep))[0]
      return int(bw_Bps*8) 


def create_graph(node_list, link_list):
      '''
      This function creates graph from node_list and link_list. Graph is a dictionary with node_id as keys and list of link objects as values
      '''
      graph = {}
      if not node_list or not link_list:
            return graph
      for node in node_list:
            links = []
            for link in link_list:
                  if link.src_node_id == node.node_id:
                        links.append(link)
            graph[node.node_id] = links
      return graph

def get_all_paths(graph, src_node_id, dest_node_id, priority, bandwidth, color_list = [], path_list=[], path=[], visited=[]):
      '''
      This function calculates all possible lsps with given constraints on bandwidth, color and returns a list of paths where each path is a list of link objects. It considers only the Traffic Engineering and RSVP enabled links while calculating the paths 
      '''
      visited.append(src_node_id)
      if src_node_id == dest_node_id:
            path_list.append(path[:])
            return path_list
      for link in graph[src_node_id]:
            if link.ted and link.dest_node_id not in visited and (not color_list or link.color in color_list) and link.unresv_bw[priority]*8 >= bandwidth:
                  path.append(link)
                  get_all_paths(graph, link.dest_node_id, dest_node_id, priority, bandwidth, color_list, path_list, path, visited)
                  visited.pop()
                  path.pop()
      return path_list 

def push_lsp(**vars):
      '''
      This function is used to create a TE tunnel in a pcc using PCEP functionality of ODL
      '''
      Variables = {
                  "pcc" : vars['pcc'],
                  "lsp_name" : vars['lsp_name'],
                  "src_ip" : vars['src_ip'],
                  "dest_ip" : vars['dest_ip'],
                  "ero_prefix" : vars['ero_prefix'],
                  "bandwidth" : base64encode(int(vars['bandwidth'])),
                  "setup_priority" : vars['setup_priority'],
                  "hold_priority" : vars['hold_priority']
      }
      with open('jinja_templates/add_lsp.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      lsp_config = model.render(Variables) 
      pushlsp_url = "http://%s:%s/restconf/operations/network-topology-pcep:add-lsp" % (ODL_IP, ODL_PORT)
      response = post_url(pushlsp_url, lsp_config)  
      if 'ODL' in response:
            return response 
      else:
            return "LSP is created successfully" 

def remove_lsp(**vars):
      '''
      This function is used to delete a TE tunnel in a pcc using PCEP functionality of ODL
      '''
      with open('jinja_templates/del_lsp.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      del_lsp_config = model.render(vars) 
      del_lsp_url = "http://%s:%s/restconf/operations/network-topology-pcep:remove-lsp" % (ODL_IP, ODL_PORT)
      response = post_url(del_lsp_url, del_lsp_config)
      if 'ODL' in response:
            return response
      else:
            return "LSP is deleted successfully"

def get_shortest_path(path_list):
      '''
      This function gets the shortest path based on igp_cost from a given path list
      '''
      path_cost =0
      for link in path_list[0]:
            path_cost = path_cost + link.igp_cost
      cost = path_cost
      shortest_path = []
      shortest_path.append(path_list[0])
      for path in path_list[1:]:
            path_cost = 0
            for link in path:
                  path_cost = path_cost + link.igp_cost
            if path_cost < cost:
                  shortest_path = []
                  shortest_path.append(path[:])
                  cost = path_cost
            elif path_cost == cost:
                  shortest_path.append(path[:])
      return shortest_path

def get_igp_all_paths(graph, src_node_id, dest_node_id, path_list=[], path=[], visited=[]):
      '''
      This function calculates shortest possible paths based on igp_costs without any constraint
      '''
      visited.append(src_node_id)
      if src_node_id == dest_node_id:
            path_list.append(path[:])
            return path_list
      for link in graph[src_node_id]:
            if link.dest_node_id not in visited:
                  path.append(link)
                  get_igp_all_paths(graph, link.dest_node_id, dest_node_id, path_list, path, visited)
                  visited.pop()
                  path.pop()
      return path_list

def get_topo_graph():
      '''
      This function is used to get the topology information from ODL and create a graph using the predefined functions
      '''
      bgp_instance = get_bgp_instances()
      if type(bgp_instance) == str:
            return bgp_instance
      try:
            get_bgpls_url = "http://%s:%s/restconf/operational/network-topology:network-topology/topology/%s" % (ODL_IP, ODL_PORT, bgp_instance[0]['instance_name'])
      except IndexError:
            return "No BGP Instance configured", "No BGP Instance configured", "No BGP Instance configured"
      get_pcep_topology = "http://%s:%s/restconf/operational/network-topology:network-topology/topology/pcep-topology/" % (ODL_IP, ODL_PORT)
      topo = get_url(get_bgpls_url)
      get_pcep = get_url(get_pcep_topology)
      if 'ODL' in topo:
            return topo, get_pcep, topo 

      node_list = []
      try:
            node_ids = []
            nonarea_prefixes ={}
            for node in topo['topology'][0]['node']:  
                  node_id = node['node-id'][node['node-id'].rfind("router=")+7:] 
                  if node_id in node_ids:
                        continue
                  if ':' in node_id:
                        # Node has IGP neighbor in broadcast network
                        node_id = node_id[:node_id.rfind(':')]       
                        continue        
                  if 'area' not in node['node-id']:
                        # Non Area 0 prefixes
                        prefixes = []
                        if 'prefix' in node['l3-unicast-igp-topology:igp-node-attributes'].keys():
                              for item in node['l3-unicast-igp-topology:igp-node-attributes']['prefix']:
                                    prefixes.append(item['prefix'])
                        nonarea_prefixes[node['node-id'][node['node-id'].rfind("router=")+7:]] = prefixes[:]
                        continue
                  router_id = ''
                  if 'router-id' in node['l3-unicast-igp-topology:igp-node-attributes'].keys():
                        router_id = node['l3-unicast-igp-topology:igp-node-attributes']['router-id'][0]
                  prefixes = []
                  if 'prefix' in node['l3-unicast-igp-topology:igp-node-attributes'].keys():
                        for item in node['l3-unicast-igp-topology:igp-node-attributes']['prefix']:
                              prefixes.append(item['prefix'])
                  if node_id in nonarea_prefixes.keys():
                        prefixes = prefixes + nonarea_prefixes[node_id]
                  pcc = ''
                  for pcc_node in get_pcep['topology'][0]['node']:
                        if pcc_node['network-topology-pcep:path-computation-client']['ip-address'] == router_id:
                              pcc = pcc_node['node-id']
                              break
                  new_node = nodes(node_id, router_id, prefixes, pcc)
                  node_ids.append(node_id)
                  node_list.append(new_node)
      except KeyError:
            logging.error('Could not get Link-State topology information from ODL') 
            return "Could not get Link-State topology information from ODL", "Could not get Link-State topology information from ODL", "Could not get Link-State topology information from ODL" 
      link_list = []
      for link in topo['topology'][0]['link']:
            src_node_id = link['source']['source-node'][link['source']['source-node'].rfind("router=")+7:] 
            nw_type = 'Point-to-Point'
            if ':' in src_node_id:
                  # Link is in broadcast network
                  src_node_id = src_node_id[:src_node_id.rfind(':')]
                  nw_type = 'Broadcast'
            src_ip = link['source']['source-tp'][link['source']['source-tp'].rfind("ipv4=")+5:] 
            dest_node_id = link['destination']['dest-node'][link['destination']['dest-node'].rfind("router=")+7:] 
            if ':' in dest_node_id:
                  # Link is in broadcast network
                  dest_node_id = dest_node_id[:dest_node_id.rfind(':')]
                  nw_type = 'Broadcast'
            dest_ip = link['destination']['dest-tp'][link['destination']['dest-tp'].rfind("ipv4=")+5:] 
            ted = '' 
            phy_bw = 0
            resv_bw = 0
            unresv_bw = {}  
            if 'max-link-bandwidth' in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted'].keys():
                  ted = "YES" 
                  phy_bw = link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted']['max-link-bandwidth']*8
            if 'max-resv-link-bandwidth' in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted'].keys():
                  resv_bw = link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted']['max-resv-link-bandwidth']*8
            if 'unreserved-bandwidth' in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted'].keys():
                  for item in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted']['unreserved-bandwidth']: 
                        unresv_bw[item['priority']] = item['bandwidth'] 
            color = ''
            if 'color' in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted'].keys():
                  color = link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted']['color']  
            ted_cost = 0 
            if 'te-default-metric' in link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted'].keys():
                  ted_cost = link['l3-unicast-igp-topology:igp-link-attributes']['ospf-topology:ospf-link-attributes']['ted']['te-default-metric'] 
            igp_cost = link['l3-unicast-igp-topology:igp-link-attributes']['metric']
            new_link = links(src_node_id, dest_node_id, src_ip, dest_ip, nw_type, ted, phy_bw, color, resv_bw, unresv_bw, igp_cost, ted_cost)
            link_list.append(new_link)
      graph = create_graph(node_list, link_list) 
      return graph, node_list, link_list

def topology_rep():
      '''
      This function returns the topology in dictionary format which can be used to represent in GUI
      '''
      graph, node_list, link_list = get_topo_graph()
      if "ODL" in graph:
            return graph 
      if not graph or type(graph) == str:
            return "No Topology Returned"
      output_dict = {}
      output_dict['nodes'] = []
      output_dict['links'] = []
      for node in node_list:
            dict1 = {}
            dict1['node_id'] = node.node_id
            if node.router_id:
                  dict1['router_id'] = node.router_id
            else:
                  dict1['router_id'] = 'Missing router-id'
            dict1['prefixes'] = node.prefixes
            output_dict['nodes'].append(dict1)
      for link in link_list:
            dict1 = {}
            dict1['link_src'] = link.src_node_id
            dict1['link_dest'] = link.dest_node_id
            dict1['nw_type'] = link.nw_type
            dict1['BW'] = link.phy_bw
            dict1['IGP_cost'] = link.igp_cost
            output_dict['links'].append(dict1)
      return output_dict


def shortest_igp_paths(**vars):
      '''
      This function returns shortest igp paths in dictionary format given src and destination IP
      '''
      src_ip = vars['src_ip']
      dest_ip = vars['dest_ip']
      graph, node_list, link_list = get_topo_graph()
      if "ODL" in graph:
            return graph  
      if not graph or type(graph) == str:
            return "Could not get link state information from ODL"
      for node in node_list:
            if node.router_id == src_ip:
                  src_node_id = node.node_id
            elif node.router_id == dest_ip:
                  dest_node_id = node.node_id 
      paths = get_shortest_path(get_igp_all_paths(graph, src_node_id, dest_node_id, path_list=[])[:])
      if not len(paths):
            return "No path with given constraints"
      path_id = 1
      shortest_paths = []
      for path in paths:
            dict = {}
            dict['path_id'] = path_id
            dict['igp_cost'] = 0
            dict['next_hop_list'] = []
            dict['hop_count'] = 0
            for link in path:
                  dict['next_hop_list'].append(link.dest_ip) 
                  dict['igp_cost'] += link.igp_cost
                  dict['hop_count'] += 1
            shortest_paths.append(dict)
            path_id += 1
      return shortest_paths


def possible_lsps(**vars):
      '''
      This function returns possible paths in dictionary format given src and destination IP and other constraints such as BW, colors. This is used for TE lsp calculation
      '''
      pcc = vars['pcc']
      lsp_name = vars['lsp_name']
      src_ip = vars['src_ip']
      dest_ip = vars['dest_ip']
      setup_priority = int(vars['setup_priority'])
      hold_priority = int(vars['hold_priority'])
      bandwidth = int(vars['bandwidth'])
      color_list = []
      if not vars['color_list']: 
            color_list.append(vars['color_list']) 
      graph, node_list, link_list = get_topo_graph()
      if "ODL" in graph:
            return graph  
      if not graph or type(graph) == str:
            return "Could not get link state information from ODL"
      for node in node_list:
            if node.router_id == src_ip:
                  src_node_id = node.node_id
            elif node.router_id == dest_ip:
                  dest_node_id = node.node_id 
            if node.router_id == pcc:
                  if not node.pcc:
                        return "Source node is not a pcc"
      paths = get_all_paths(graph, src_node_id, dest_node_id, setup_priority, bandwidth, color_list, path_list=[])[:]
      if not len(paths):
            return "No path with given constraints"
      path_id = 1
      possible_lsp = []
      for path in paths:
            dict = {}
            dict['path_id'] = path_id
            dict['igp_cost'] = 0
            dict['ted_cost'] = 0
            dict['next_hop_list'] = []
            dict['hop_count'] = 0
            for link in path:
                  dict['next_hop_list'].append(link.dest_ip) 
                  dict['igp_cost'] += link.igp_cost
                  dict['ted_cost'] += link.ted_cost
                  dict['hop_count'] += 1
            possible_lsp.append(dict)
            path_id += 1
      return possible_lsp 

def get_bgp_instances():
      '''
      This function is used to get the details of BGP Instance configured in ODL.
      '''
      bgp_instance_url = "http://%s:%s/restconf/operational/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols" % (ODL_IP, ODL_PORT)
      bgp_instances = get_url(bgp_instance_url)  
      if bgp_instances == "Error from ODL or incorrect API call":
            return "No BGP Instance configured in ODL" 
      if 'ODL' in bgp_instances:
            return bgp_instances
      instance_list = []
      for instance in bgp_instances['protocols']['protocol']:
            if 'bgp-openconfig-extensions:bgp' in instance.keys() and instance['name'] != 'example-bgp-rib':
                  for afi in instance['bgp-openconfig-extensions:bgp']['global']['afi-safis']['afi-safi']:
                        if 'LINKSTATE' in afi['afi-safi-name']:
                              break
                  else:
                        continue      
                  dict = {}
                  dict['instance_name'] = instance['name']
                  dict['router_id'] = instance['bgp-openconfig-extensions:bgp']['global']['state']['router-id']
                  dict['AS'] = instance['bgp-openconfig-extensions:bgp']['global']['state']['as']    
                  instance_list.append(dict)
      return instance_list 

def add_bgp_instance(**vars):
      '''
      Function to add a bgp instance in ODL. Only one BGP instance can be added in ODL. Configured BGP router-id should be reachable to neighbors
      '''
      bgp_instance_url = "http://%s:%s/restconf/config/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols" % (ODL_IP, ODL_PORT)
      topology_url = "http://%s:%s/restconf/config/network-topology:network-topology/" % (ODL_IP, ODL_PORT)
      with open('jinja_templates/add_bgp_instance.j2') as f:
                  template = f.read()
      model = jinja2.Template(template)
      bgp_instance_config = model.render(vars) 
      with open('jinja_templates/add_topology.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      bgp_topology_config = model.render(vars) 
      response =  post_url(bgp_instance_url, bgp_instance_config)
      if 'ODL' in response:
            return response 
      else:
            post_url(topology_url, bgp_topology_config)
            return "BGP-instance added successfully"


def del_bgp_instance(instance_name):
      '''
      Function to delete BGP Instance in ODL
      '''
      bgp_instance_url = "http://%s:%s/restconf/config/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols" % (ODL_IP, ODL_PORT)
      topology_url = "http://%s:%s/restconf/config/network-topology:network-topology/" % (ODL_IP, ODL_PORT)
      vars = {}
      vars['instance_name'] = instance_name
      with open('jinja_templates/del_bgp_instance.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      bgp_instance_config_del = model.render(vars)
      with open('jinja_templates/del_topology.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      bgp_topology_config_del = model.render(vars)
      response = delete_url(topology_url, bgp_topology_config_del)
      delete_url(bgp_instance_url, bgp_instance_config_del)
      if response == "Error from ODL or incorrect API call":
            return str("No such BGP Instance configured")
      if 'ODL' in response:
            return response
      else:
            return "BGP-instance deleted successfully"

 
def get_bgpls_peers(bgp_instance):
      '''
      Function to get a list of BGP LS neighbors
      '''
      bgpls_peer_url = "http://%s:%s/restconf/operational/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols/protocol/openconfig-policy-types:BGP/%s/bgp/neighbors" % (ODL_IP, ODL_PORT, bgp_instance) 
      bgpls_peers =  get_url(bgpls_peer_url)
      if bgpls_peers == "Error from ODL or incorrect API call":
            return "There is no BGPLS peer configured in ODL"  
      if 'ODL' in bgpls_peers:
            return bgpls_peers
      peer_list = []
      for neighbor in bgpls_peers['bgp-openconfig-extensions:neighbors']['neighbor']:
            dict = {}
            dict['neighbor_address'] = neighbor['neighbor-address']
            try:
                  dict['state'] = neighbor['state']['session-state']
                  dict['uptime'] = neighbor['timers']['state']['uptime']
                  dict['remote_port'] = neighbor['transport']['state']['remote-port']
            except KeyError:
                  dict['state'] = 'Idle'
                  dict['remote_port'] = -1 
                  dict['uptime'] = -1 
                
            for afi in neighbor['afi-safis']['afi-safi']:
                  if  afi['afi-safi-name'] == 'bgp-openconfig-extensions:LINKSTATE':
                        if afi['state']['active']:
                              dict['LINKSTATE_Status'] = 'Active' 
                              break
                        else:
                              dict['LINKSTATE_Status'] = 'Idle'
                              break
            peer_list.append(dict)
      return peer_list 

def add_bgpls_neigh(**vars):
      '''
      Function to add a BGP LS neighbor.
      '''
      bgpls_peer_url = "http://%s:%s/restconf/config/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols/protocol/openconfig-policy-types:BGP/%s/bgp/neighbors" % (ODL_IP, ODL_PORT, vars['bgp_instance']) 
      with open('jinja_templates/add_bgpls_peer.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      bgpls_peer_config = model.render(vars)
      response = post_url(bgpls_peer_url, bgpls_peer_config)
      if 'ODL' in response:
            return response
      else:
            return "BGP-LS peer is successfully added" 
 
def del_bgpls_neigh(**vars):
      '''
      Function to delete a BGP LS neighbor.
      '''
      bgpls_peer_url = "http://%s:%s/restconf/config/openconfig-network-instance:network-instances/network-instance/global-bgp/openconfig-network-instance:protocols/protocol/openconfig-policy-types:BGP/%s/bgp/neighbors/neighbor/%s" % (ODL_IP, ODL_PORT, vars['bgp_instance'], vars['peer_ip']) 
      with open('jinja_templates/del_bgpls_peer.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      bgpls_peer_config = model.render(vars)
      response = delete_url(bgpls_peer_url, bgpls_peer_config)
      if response == "Error from ODL or incorrect API call":
            return str("No such BGP-LS neighbor configured")
      if 'ODL' in response:
            return response 
      else:
            return "BGP-LS peer is successfully deleted"

def topology_reset(**vars):
      '''
      To do a topology refresh in ODL. This is needed because sometimes ODL does get proper topology information
      '''
      with open('jinja_templates/topo_reset.j2') as f:
            template = f.read()
      model = jinja2.Template(template)
      topo_reset_config = model.render(vars) 
      topo_reset_url = "http://%s:%s/restconf/config/network-topology:network-topology/" % (ODL_IP, ODL_PORT) 
      response1 = delete_url(topo_reset_url, topo_reset_config)
      response2 = post_url(topo_reset_url, topo_reset_config)
      if 'ODL' in response1 or 'ODL' in response2: 
            return response1 + " " + response2 + " Topology could not be reset"  
      else:
            return "Topology has been reset"

def get_pcc_list():
      '''
      Gets a list of devices configured as Path-Computation Elements.
      '''
      pcc_url = "http://%s:%s/restconf/operational/network-topology:network-topology/topology/pcep-topology/" % (ODL_IP, ODL_PORT)
      pcc_list = get_url(pcc_url)
      if pcc_list == "Error from ODL or incorrect API call":
            return "There is no PCC configured" 
      if 'ODL' in pcc_list:
            return pcc_list
      list = []
      try:
            for pcc in pcc_list['topology'][0]['node']:
                  dict = {}
                  dict['node_id'] = pcc['node-id']
                  dict['sync_state'] = pcc['network-topology-pcep:path-computation-client']['state-sync']
                  dict['ip_address'] = pcc['network-topology-pcep:path-computation-client']['ip-address']
                  list.append(dict) 
      except:
            return "There is no PCC configured" 
      return list

def get_reported_lsp(pcc):
      '''
      Gets a list of already established TE tunnels from PCCs
      '''
      lsp_url = "http://%s:%s/restconf/operational/network-topology:network-topology/topology/pcep-topology/node/pcc:%%2F%%2F%s" % (ODL_IP, ODL_PORT, pcc)  
      lsp_data = get_url(lsp_url) 
      if lsp_data == 'Error from ODL or incorrect API call':
            return str("%s is not configured as PCC" % (pcc))
      if 'ODL' in lsp_data:
            return lsp_data 
      lsp_list = []
      try:
            for lsps in lsp_data['node'][0]['network-topology-pcep:path-computation-client']['reported-lsp']:
                  dict = {}
                  dict['name'] = lsps['name']
                  dict['paths'] = []
                  for path in lsps['path']:
                        lsp = {}
                        prefix_list = []
                        for prefix in path['ero']['subobject']:
                              prefix_list.append(prefix['ip-prefix']['ip-prefix'])
                        lsp['hop_list'] = prefix_list[:]
                        lsp['operational_state'] = path['odl-pcep-ietf-stateful07:lsp']['operational']
                        lsp['source_ip'] = path['odl-pcep-ietf-stateful07:lsp']['tlvs']['lsp-identifiers']['ipv4']['ipv4-tunnel-sender-address']
                        lsp['destination_ip'] = path['odl-pcep-ietf-stateful07:lsp']['tlvs']['lsp-identifiers']['ipv4']['ipv4-tunnel-endpoint-address']
                        lsp['tunnel_id'] = path['odl-pcep-ietf-stateful07:lsp']['tlvs']['lsp-identifiers']['tunnel-id']
                        lsp['delegation'] = path['odl-pcep-ietf-stateful07:lsp']['delegate']
                        lsp['bandwidth'] = base64decode(path['bandwidth']['bandwidth'])
                        lsp['setup_priority'] = path['lspa']['setup-priority']
                        lsp['hold_priority'] = path['lspa']['hold-priority']
                        dict['paths'].append(lsp) 
                  lsp_list.append(dict)
      except KeyError: 
            return str("There is no Tunnel configured in PCC: %s" % (pcc))
      return lsp_list[:]
 
if __name__ == "__main__":
      print topology_rep()