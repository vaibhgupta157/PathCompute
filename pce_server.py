import flask
from flask import request, jsonify, abort, render_template, flash, redirect, url_for
import odl_bgp_ls
import argparse, sys
import logging
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter

logging.basicConfig(filename='logs/odl_bgp.log', level=logging.INFO)
 
app = flask.Flask(__name__)
app.secret_key = "super secret key"
app.config["DEBUG"] = True

tunnel_vars = {}
path_list = []
pcc = ''

reload(sys)
sys.setdefaultencoding("utf-8")

@app.route('/pce/')
def home():
     maininputs = {}
     topology = odl_bgp_ls.topology_rep()
     if type(topology) == str:
          maininputs['nodes'] = []
          maininputs['links'] = []
     else:
          maininputs['nodes'] = topology['nodes']
          maininputs['links'] = topology['links']
     maininputs['BGP_Instance'] = ''
     maininputs['localas'] = ''
     maininputs['router_id'] = ''
     bgp_instances = odl_bgp_ls.get_bgp_instances()
     if bgp_instances and isinstance(bgp_instances, list):
          maininputs['BGP_Instance'] = str(bgp_instances[0]['instance_name'])
          maininputs['localas'] = str(bgp_instances[0]['AS'])
          maininputs['router_id'] = str(bgp_instances[0]['router_id'])
     neighbors = ''
     if maininputs['BGP_Instance']:
          neighbors = odl_bgp_ls.get_bgpls_peers(maininputs['BGP_Instance'])
     if isinstance(neighbors, list):
          maininputs['neighbors'] = neighbors
     pccs = odl_bgp_ls.get_pcc_list()
     if isinstance(pccs, list):
           maininputs['pccs'] = pccs     
     return render_template('home1.html', **maininputs)  

@app.route('/pce/possible_lsps/', methods=['POST'])
def lsps_with_constraints():
     global tunnel_vars, path_list
     tunnel_vars = {
          "pcc" : request.form['pcc'].strip(),
          "lsp_name" : request.form['lsp_name'].strip(),
          "src_ip" : request.form['src_ip'].strip(),
          "dest_ip" : request.form['dest_ip'].strip(),
          "setup_priority" : request.form['setup_priority'].strip(),
          "hold_priority" : request.form['hold_priority'].strip(),
          "bandwidth" : request.form['bandwidth'].strip(),
          "color_list" : request.form['color_list'].split(",")
     }
     path_list = odl_bgp_ls.possible_lsps(**tunnel_vars)
     if type(path_list) == str:
          flash(path_list)
          return redirect(url_for('home'))
     else:
          logging.info("Possible LSPS calculated successfully")
          for path in path_list:
               path['next_hop_list'] = ",".join(path['next_hop_list'])
          inputs={'path_list':path_list}
          return render_template('lsp.html', **inputs)
        

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

@app.route('/pce/push_lsp/', methods=['POST'])
def push_lsp():
     path_id = request.form['path_id']
     variables = tunnel_vars
     variables['ero_prefix'] = path_list[int(path_id)-1]['next_hop_list'].split(",")[:]
     response =  odl_bgp_ls.push_lsp(**variables) 
     flash(response)
     return redirect(url_for('home'))   

@app.route('/pce/remove_lsp/', methods=['POST']) 
def remove_lsp():
     variables = {
          "pcc" : pcc,
          "lsp_name" : request.form['lsp_name']
     }
     response = odl_bgp_ls.remove_lsp(**variables)
     flash(response)
     return redirect(url_for('home'))

@app.route('/pce/pcc_list/', methods=['GET'])
def get_pcc_list():
     pcc_list = odl_bgp_ls.get_pcc_list()
     if type(pcc_list) == str:
          flash(pcc_list)
          return redirect(url_for('home'))
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
     if type(instances) == str and instances == "No BGP Instance configured in ODL":
          vars = {}
          vars["instance_name"] = str(request.form["instance_name"].strip())
          vars["router_id"] = str(request.form["router_id"].strip())
          vars["local_as"] = int(request.form["local_as"].strip())
          response = odl_bgp_ls.add_bgp_instance(**vars)
          flash(response)
          return redirect(url_for('home'))
     if type(instances) == str:
          flash("Unable to get configuration from ODL")
          return redirect(url_for('home'))
     if instances:
          flash("Already one BGP Instance exists. Please delete the existing BGP instance first")
          return redirect(url_for('home'))


@app.route('/pce/bgp_instances/<instance_name>', methods=['POST'])
def del_bgp_instances(instance_name):
     response = odl_bgp_ls.del_bgp_instance(instance_name)
     flash(response)
     return redirect(url_for('home'))

@app.route('/pce/established_lsps/', methods=['POST'])
def established_lsps():
     try:
          global pcc
          pcc = request.form["pcclient"].strip()
     except KeyError as e:
          logging.error(e)
          flash("Select a PCC first")
          return redirect(url_for('home'))
     established_lsps = odl_bgp_ls.get_reported_lsp(pcc)
     if type(established_lsps) == str:
          flash(established_lsps)
          return redirect(url_for('home'))
     else:
          lsps = {'established_lsps' : established_lsps}
          return render_template('estblsps.html', **lsps)

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
     bgp_instance = ''
     instances = odl_bgp_ls.get_bgp_instances()
     if type(instances) == str:
          flash(instances)
          return redirect(url_for('home'))
     if not instances:
          flash("Create BGP Instance first")
          return redirect(url_for('home'))
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          flash("Create BGP Instance first")
          return redirect(url_for('home'))
     vars={}
     vars['bgp_instance'] = bgp_instance
     vars['peer_ip'] = request.form['peer_ip'].strip()
     vars['hold_time'] = "90"
     vars['connectretry_timer'] = "10"
     vars['remote_port'] = "179"
     vars['passive_mode'] = "false"
     response =  odl_bgp_ls.add_bgpls_neigh(**vars)
     flash(response)
     return redirect(url_for('home'))
 
@app.route('/pce/del-ls-peer/', methods=['POST'])
def del_bgpls_peer():
     instances = odl_bgp_ls.get_bgp_instances()
     bgp_instance = ''
     if type(instances) == str:
          flash(instances)
          return redirect(url_for('home'))
     if not instances:
          flash("Create BGP Instance first")
          return redirect(url_for('home'))
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          flash("Create BGP Instance first")
          return redirect(url_for('home'))
     try:
          vars = {
               "bgp_instance" : bgp_instance,
               "peer_ip" : request.form['peer_ip']
          }
     except KeyError as e:
          logging.error(e)
          flash("Select a peer to be deleted")
          return redirect(url_for('home'))
     response = odl_bgp_ls.del_bgpls_neigh(**vars)
     flash(response)
     return redirect(url_for('home'))

@app.route('/pce/topology_reset/', methods=['POST'])
def Topology_reset():
     instances = odl_bgp_ls.get_bgp_instances() 
     bgp_instance = ''
     for inst in instances:
          if inst['instance_name'] != 'example-bgp-rib':
               bgp_instance = inst['instance_name']
               break
     if not bgp_instance:
          flash("Create BGP Instance first")
          return redirect(url_for('home'))
     vars = {
         "instance_name" : bgp_instance
     }
     response = odl_bgp_ls.topology_reset(**vars)
     flash(response)
     return redirect(url_for('home'))

if __name__ == '__main__':
     app.run(host='0.0.0.0', port=9521)
