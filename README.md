# PathCompute
PathCompute is developed on top of ODL to represent topology in UI based on information from Link-State database. It also exposes REST APIs for calculating constraints based LSPs for TE and getting IGP path between a pair of src and dest. 

# PreRequisites:
apt-get install python-pip
pip install flask requests

# ODL Setup:
cd karaf**
./bin/karaf
feature:install odl-restconf odl-bgpcep-bgp-l3vpn odl-bgpcep-bgp-openconfig-state 
^d
./bin/start

# Enter ODL details in odl_details.py
ODL_IP = "xx.xx.xx.xx"
ODL_PORT = "8181"
ODL_USER = "admin"
ODL_PASS = "admin"

# Run pce_server.py
python pce_server.py

REST APIs:
Create BGP instance:
POST http://xx.xx.xx.xx:9521/pce/bgp_instances/
  {
    "instance_name" : "name",
    "router_id" : "xx.xx.xx.xx",
    "local_as" : "AS No"
  }
  
Add a BGP-LS Neighbor:
POST http://xx.xx.xx.xx:9521/pce/add-ls-peer/
  {
    "peer_ip" : "xx.xx.xx.xx",
    "hold_time" : "90",
    "connectretry_timer" : "10",
    "remote_port" : "179",
    "passive_mode" : "false"
  }
 
Once Neighbor is UP:
Open Url in browser:
http://xx.xx.xx.xx:9521/pce/

refer REST.doc for more API calls
