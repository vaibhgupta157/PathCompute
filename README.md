[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/vaibhgupta157/PathCompute)


# PathCompute
PathCompute is developed on top of ODL to represent topology in UI based on information from Link-State database. It can be used for calculating constraints based LSPs for RSVP-TE and pushing those tunnels to Path Computation Client. It also exposes REST APIs for calculating IGP path between a pair of src and dest. 

# PreRequisites:
The app is developed using python and require following additional packages to work.\
apt-get install python-pip\
pip install flask requests

# ODL Setup:
This repo requires additional plugins for bgp, pcep and restconf in opendaylight. It is recommended to use Opendaylight Nitrogen release.

cd karaf**\
./bin/karaf\
feature:install odl-restconf odl-bgpcep-bgp odl-bgpcep-bgp-openconfig-state odl-bgpcep-pcep\
^d \
./bin/start

# Enter ODL details in odl_details.py
ODL_IP = "xx.xx.xx.xx"\
ODL_PORT = "8181"\
ODL_USER = "admin"\
ODL_PASS = "admin"

# Run pce_server.py
python pce_server.py

Open in Browser:\
http://xx.xx.xx.xx:9521/pce/ 

![PathCompute](https://user-images.githubusercontent.com/44111751/61218222-29513480-a72f-11e9-8554-a900a1c3cc4a.JPG)


To start with add a bgp instance with link-state address-family in Opendaylight by clicking "Add Instance". Specify the local router-id  (which has to be an interface IP address on the linux machine on which Opendaylight is installed) and AS number. Once bgp instance is added, add atleast one bgp-ls peer by clicking "Add Peer". A BGP-LS peer is a router which is enabled with link-state address family and is part of IGP. The BGP session between Opendaylight and router(Peer) comes up after BGP protocol negotiation and status can be seen in UI. Opendaylight router-id should be reachable to router's BGP router-id. 

Once LS-peer state is "Established" and Linkstate is "Active", IGP topology can be seen in right half. Topology captures point-to-point and broadcast network-type by highlighting with grey and blue color respectively. To have topology view in UI LS-peer should distribute IGP in BGP link-state.

Tunnel Manager section manages RSVP-TE for the nodes in network which are configured as Path Computation Clients(PCCs). List of PCCs can be seen from Get PCCs and their established tunnels. A new tunnel can be pushed to any PCC by using "Create Tunnel". It lists all possible LSPs with given constraints and corresponding IGP and TE metrics. One of them can be pushed to PCC by clicking "Push LSP". The app considers only the interfaces which are enabled with traffic engineering for path calculation
