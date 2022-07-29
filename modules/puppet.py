import cx_Oracle
import json, socket
from flask import Blueprint, request, Response, current_app, g

blueprint = Blueprint('puppet', __name__, url_prefix='/puppet')

@blueprint.before_request
def initialise():
    g.dbconn = cx_Oracle.connect(current_app.config['CMDB_USER'],current_app.config['CMDB_PASSWD'],current_app.config['CMDB_SID'])
    g.cursor = g.dbconn.cursor()

@blueprint.teardown_request
def disconnect(exc=None):
    try:
	if g.dbconn:
	    g.dbconn.close()
    except:
	pass

@blueprint.route('/networkdetails/<hostname>',methods=['GET'])
def get_network_details(hostname):
    try:
	# retrieve the IP address of the supplied hostname
	current_app.logger.info('Performing DNS lookup for %s' % hostname)

	try:
	    (host,dot,domain) =  socket.getfqdn(hostname).partition('.')
	    ipaddress = socket.gethostbyname(host)
	except Exception as e:
	    current_app.logger.exception(str(e))
	    return Response(json.dumps({'object':'DNS','exception':str(e)}),status=404,mimetype='application/json')

	ipaddress_tokens = ipaddress.split('.')
	first_three_octets = ".".join(ipaddress_tokens[0:3])
	ip_last_octet = ipaddress_tokens[-1]

	g.cursor.execute("select ADDRESS, NETMASK, GATEWAY, SPEED, VLAN, PCI, DMZ from ASP_RSCE.ASP_NETWORK where ADDRESS like '" + first_three_octets + ".%'")

	# store all the rows where the network address' first three octets match the
	# first three octets of the supplied host's IP address
	matches = {}

	for r in g.cursor:
	    matches[r[0]] = {}
            matches[r[0]]['network'] = r[0]
            matches[r[0]]['netmask'] = r[1]
            matches[r[0]]['gateway'] = r[2]
            matches[r[0]]['speed']   = r[3]
            matches[r[0]]['vlanid']  = r[4]
            matches[r[0]]['pci']     = r[5]
            matches[r[0]]['dmz']     = r[6]

	if not matches:
	    raise Exception('Cannot find network details for ip %s' % ipaddress)

	if len(matches) == 1:

	    result = matches[matches.keys()[0]]

	else:
	    prev_key = None
	    for net_address in sorted([int(x.split('.')[3]) for x in matches.keys()]):
		if net_address > int(ip_last_octet):
		    if not prev_key:
			raise Exception('Cannot find network details for ip %s' % ipaddress)
		    break
		else:
		    prev_key = '%s.%s' % (first_three_octets,net_address)

	    result = matches[prev_key]

	# add the ipaddress and the domain to the hash
	result['ipaddress'] = ipaddress
	result['domain']    = domain

	return Response(json.dumps(result),status=200,mimetype='application/json')

    except Exception as e:
	current_app.logger.exception(str(e))
	return Response(json.dumps({'object':'RAPI','exception':str(e)}),status=500,mimetype='application/json')
