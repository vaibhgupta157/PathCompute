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

