import flask
from flask import request, jsonify, abort, render_template
import odl_bgp_ls
import logging
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter

logging.basicConfig(filename='logs/odl_bgp.log', level=logging.INFO)
 
app = flask.Flask(__name__)
app.config["DEBUG"] = True

tunnel_vars = {}
path_list = []

@app.route('/pce/')
def home():
     topology = odl_bgp_ls.topology_rep()
     if type(topology) == str:
          return '<HTML><BODY><H2>Could not get Link State Information from ODL</H2></BODY></HTML>'
     return render_template('main.html', **topology)  

@app.route('/pce/possible_lsps/', methods=['POST'])
def lsps_with_constraints():
     if not request.json:
          abort(400)
     global tunnel_vars, path_list
     tunnel_vars = request.json
     path_list = odl_bgp_ls.possible_lsps(**tunnel_vars)
     if type(path_list) == str:
          logging.error(path_list)
          return jsonify(Error = path_list), 400
     else:
          logging.info("Possible LSPS calculated successfully")
          return jsonify(possible_paths = path_list)
        

@app.route('/pce/igp_paths/', methods=['POST'])
def igp_paths():
     if not request.json:
          abort(400)
     vars = request.json
     path_list = odl_bgp_ls.shortest_igp_paths(**vars)
     if type(path_list) == str:
          logging.error(path_list)
          return jsonify(Error = path_list), 400 
     else:
          logging.info("IGP path calculated successfully")
          return jsonify(shortest_paths = path_list)

@app.route('/pce/push_lsp/<path_id>/', methods=['POST'])
def push_lsp(path_id):

     variables = tunnel_vars
     variables['ero_prefix'] = path_list[int(path_id)-1]['next_hop_list'][:]
     response =  odl_bgp_ls.push_lsp(**variables) 
     if 'ODL' in response:
          logging.error(response)
          return jsonify(Error = response), 400
     else:
          logging.info(response)
          return jsonify(Success = response)     

@app.route('/pce/remove_lsp/<pcc>/<lsp_name>', methods=['POST']) 
def remove_lsp(pcc, lsp_name):
     variables = {
          "pcc" : pcc,
          "lsp_name" : lsp_name
     }
     response = odl_bgp_ls.remove_lsp(**variables)
     if 'ODL' in response:
          return jsonify(Error = response), 400
     else:
          return jsonify(Success = response)

@app.route('/pce/pcc_list/', methods=['GET'])
def get_pcc_list():
     pcc_list = odl_bgp_ls.get_pcc_list()
     if type(pcc_list) == str:
          logging.error(pcc_list)
          return jsonify(Error = pcc_list), 400
     else: 
          logging.info("Successfully got PCC list")
          return jsonify(pcc_list = pcc_list) 

@app.route('/pce/bgp_instances/', methods=['GET'])
def get_bgp_instances():
     bgp_instances = odl_bgp_ls.get_bgp_instances()
     if type(bgp_instances) == str:
          logging.error(bgp_instances)
          return jsonify(Error = bgp_instances), 400
     elif not bgp_instances:
          logging.error("No BGP-LS instance configured")
          return jsonify(Error = "There is no BGP-LS instance configured. BGP-LS instance with atleast one peer is required"), 400
     else:   
          logging.info("BGP Instance information fetched successfully")
          return jsonify(bgp_instances = bgp_instances)

@app.route('/pce/bgp_instances/', methods=['POST'])
def add_bgp_instances():
     instances = odl_bgp_ls.get_bgp_instances()
     bgp_instance = ''
     if type(instances) == str:
          return jsonify(Error = "Unable to get configuration from ODL"), 400
     if instances:
          return jsonify(Error = "Already one BGP Instance exists. Please delete the existing BGP instance first"), 400
     vars = request.json 
     response = odl_bgp_ls.add_bgp_instance(**vars)
     if 'ODL' in response:
          return jsonify(Error = response), 400
     else:
          return jsonify(success = response) 

@app.route('/pce/bgp_instances/<instance_name>', methods=['DELETE'])
def del_bgp_instances(instance_name):
     response = odl_bgp_ls.del_bgp_instance(instance_name)
     if 'ODL' in response:
          return jsonify(Error = response), 400
     else:
          return jsonify(success = response)

@app.route('/pce/established_lsps/<pcc>/', methods=['GET'])
def established_lsps(pcc):
     established_lsps = odl_bgp_ls.get_reported_lsp(pcc)
     if type(established_lsps) == str:
          return jsonify(Error = established_lsps), 400
     else:
          return jsonify(established_lsps = established_lsps) 

@app.route('/pce/get-ls-peers/', methods=['GET'])
def get_bgpls_peer():
     instances = odl_bgp_ls.get_bgp_instances()
     bgp_instance = ''
     if type(instances) == str:
          return jsonify(Error = instances), 400
     if not instances:
          return jsonify(Error = "Create BGP Instance first"), 400
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          return jsonify(Error = "Create BGP Instance first"), 400
     peer_list = odl_bgp_ls.get_bgpls_peers(bgp_instance)
     if type(peer_list) == str:
          return jsonify(Error = peer_list), 400
     else:
          return jsonify(neighbors = peer_list)
   
@app.route('/pce/add-ls-peer/', methods=['POST'])
def add_bgpls_peer():
     if not request.json:
          abort(400)
     bgp_instance = ''
     instances = odl_bgp_ls.get_bgp_instances()
     if type(instances) == str:
          return jsonify(Error = instances), 400
     if not instances:
          return jsonify(Error = "Create BGP Instance first"), 400
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          return jsonify(Error = "Create BGP Instance first"), 400 
     vars = request.json
     vars['bgp_instance'] = bgp_instance
     response =  odl_bgp_ls.add_bgpls_neigh(**vars)
     if 'ODL' in response:  
          return jsonify(Error = response), 400
     else: 
          return jsonify(success = response) 
 
@app.route('/pce/<peer_ip>/', methods=['DELETE'])
def del_bgpls_peer(peer_ip):
     instances = odl_bgp_ls.get_bgp_instances()
     bgp_instance = ''
     if type(instances) == str:
          return jsonify(Error = instances), 400
     if not instances:
          return jsonify(Error = "Create BGP Instance first"), 400
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          return jsonify(Error = "Create BGP Instance first"), 400
     vars = {
         "bgp_instance" : bgp_instance,
         "peer_ip" : peer_ip
     }
     response = odl_bgp_ls.del_bgpls_neigh(**vars)
     if 'ODL' in response:
          return jsonify(Error = response), 400
     else:
          return jsonify(success = response)

@app.route('/pce/topology_reset/', methods=['POST'])
def Topology_reset():
     instances = odl_bgp_ls.get_bgp_instances() 
     bgp_instance = ''
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          return jsonify(Error = "Create BGP Instance first"), 400
     vars = {
         "bgp_instance" : bgp_instance
     }
     response = odl_bgp_ls.topology_reset(**vars)
     if 'ODL' in response:
          return jsonify(Error = response), 400
     else:
          return jsonify(success = response)

if __name__ == '__main__':
     app.run(host='0.0.0.0', port=9521)
