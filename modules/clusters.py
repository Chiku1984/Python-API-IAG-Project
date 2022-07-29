import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

from ba_rapi.Oasis import Oasis

blueprint = Blueprint('clusters', __name__, url_prefix='/clusters')

@blueprint.before_request
def initialise():
    g.oasis = Oasis(baseurl='http://esmapi-dev.baplc.com/oasis/appl',apikey='fad84f06-97d7-4a63-8433-d5abf6f3ff67')
    g.redis = REDIShelper(host=current_app.config['REDIS_HOST'],
			  port=current_app.config['REDIS_PORT'],
			  db=current_app.config['REDIS_DB'])
    g.rhev  = RHEVhelper()


@blueprint.route('/<cluname>/hosts', methods=['GET'])
@requires_auth
def getHosts(cluname):
    try:
        current_app.logger.info('Processing request for cluster %s hosts' % cluname)
        g.rhevapi = g.rhev.getAPI(cluname)
        clu_hosts = g.rhevapi.Cluster.listHosts(cluname)
    except Exception as e:
        current_app.logger.exception('EXCEPTION getting hosts for RHEV cluster %s' % cluname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),
                                   status=400,mimetype='application/json')

    hosts = [ x.name for x in clu_hosts ]

    # return a good response - phew!
    return Response(json.dumps({'hosts':hosts}),status=200,mimetype='application/json')


@blueprint.route('/<cluname>/networks', methods=['GET'])
@requires_auth
def getNetworks(cluname):
    try:
	current_app.logger.info('Processing request for network details for cluster %s' % cluname)
	g.rhevapi = g.rhev.getAPI(cluname)
	clu_networks = g.rhevapi.Cluster.listNetworks(cluname) 
    except Exception as e:
	current_app.logger.exception('EXCEPTION retrieving network details for RHEV cluster %s' % cluname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),
				   status=400,mimetype='application/json')

    networks = []
 
    for net in clu_networks:
	if net.name in [ 'rhevm', 'ovirtmgmt' ]:
	    continue

	try:
	    desc = net.description
	except:
	    desc = None

	try:
	    vlanid = net.vlan.id
	except:
	    vlanid = None

	networks.append({ 'name' : net.name, 'description' : desc, 'vlanid' : vlanid })

    # return a good response - phew!
    return Response(json.dumps({'networks':networks}),status=200,mimetype='application/json')


@blueprint.route('/<cluname>/networks', methods=['POST'])
@requires_auth
def addNetworks(cluname):
    # process request JSON
    try:
	current_app.logger.info('Processing request to add network to cluster')
	request_json = request.json
	current_app.logger.debug("Request JSON : %s" % request_json)

	if 'vlanid' not in request_json:
	    raise Exception("Request json must contain a 'vlanid' element")

    except Exception as e:
	current_app.logger.exception('Exception processing cluster network addition')
	return Response(json.dumps({'object':'REQUEST','exception':"Exception raised handling request : %s" % str(e)}),
				    status=400,mimetype='application/json')

    # connect to RHEV and attempt cluster network addition
    try:
	current_app.logger.info('Adding vlanid %s to cluster %s' % (request_json['vlanid'],cluname))
	g.rhevapi = g.rhev.getAPI(cluname)
	network = g.rhevapi.Cluster.addNetwork(cluster = cluname, **request_json)

    except Exception as e:
	current_app.logger.exception('EXCEPTION adding vlanid %s to cluster %s' % (request_json['vlanid'],cluname))
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=400,mimetype='application/json')

    # add the network to the cluster hosts
    try:
	for host in g.rhevapi.Cluster.listHosts(cluname):
	    current_app.logger.info('Configuring network %s to host %s' % (network.name,host.name))
	    g.rhevapi.Host.addNetwork(hostname=host.name,network=network)

    except Exception as e:
	current_app.logger.exception('EXCEPTION adding network %s to cluster hosts' % network.name)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=400,mimetype='application/json')

    # return a good response
    return Response(status=200)


@blueprint.route('/<cluname>/networks/<vlanid>', methods=['DELETE'])
@requires_auth
def removeNetworkByVLANID(cluname,vlanid):
    try:
	current_app.logger.info('Processing request to remove network with VLAN ID %s from cluster %s' % (vlanid,cluname))
	g.rhevapi = g.rhev.getAPI(cluname)
	
	try:
	    current_app.logger.info('Retrieving networks from cluster %s' % cluname)
	    
	    clu_networks = g.rhevapi.Cluster.listNetworks(cluname)
	    
	    if not clu_networks:
		raise Exception('Cluster does not exist - or contains no networks!')

	    #current_app.logger.info(

	    #network = next((x for x in clu_networks if x.vlan and (x.vlan.id == vlanid)), None)

	    network = None

	    for x in clu_networks:
		try:
		    current_app.logger.info('Network %s has vlan id %s %s' % (x.name,x.vlan.id,str(vlanid)))
		    if int(x.vlan.id) == int(vlanid):
			network = x
			break
	 	except:
		    pass

	    if not network:
		raise Exception('No network with vlanid %s in cluster %s' % (vlanid,cluname))

	except Exception as e:
	    current_app.logger.exception(str(e))
	    return Response(status=404)

	current_app.logger.info('Removing network %s from cluster %s' % (network.name,cluname))
	network.delete()

    except Exception as e:
	current_app.logger.exception('EXCEPTION removing network %s from cluster %s' % (network.name,cluname))
        return Response(json.dumps({'object':'RHEV','exception':str(e)}), status=400,mimetype='application/json')

    try:
	current_app.logger.info('Removing network %s from cluster %s\'s hosts' % (network.name,cluname))

	for cluhost in g.rhevapi.Cluster.listHosts(cluname):
	    current_app.logger.debug('Removing network %s from host %s' % (network.name,cluhost.name))
	    try:
		g.rhevapi.Host.removeNetwork(hostname=cluhost.name,network=network)
	    except ValueError as e:
		current_app.logger.exception('Network %s does not appear to be configured on host %s' % (network.name,cluname))

    except Exception as e:
	current_app.logger.exception('EXCEPTION removing network %s from cluster %s\'s hosts' % (network.name,cluname))
        return Response(json.dumps({'object':'RHEV','exception':str(e)}), status=400,mimetype='application/json')

    return Response(status=200)


@blueprint.route('/<cluname>/storage', methods=['GET'])
@requires_auth
def getStorage(cluname):
    try:
	current_app.logger.info('Processing request for storagedomains for cluster %s')
	g.rhevapi = g.rhev.getAPI(cluname)
	DC = g.rhevapi.Cluster.getDatacenter(cluname) 
        STORAGEDOMAINS = g.rhevapi.DataCenter.getStorageDomains(DC.name)
    except Exception as e:
	current_app.logger.exception('EXCEPTION retrieving storage domains for cluster %s' % cluname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}), status=400,mimetype='application/json')

    storage = []

    # process the 'raw' storage domain output
    try:
	manager = g.rhev.getManagerNameFromCache(cluname)
	rediskey = 'oasis:rhev:datacentres:%s:%s:%s' % (manager,DC.name,DC.id)
	g.redis.set(rediskey,json.dumps(g.oasis.Datacentre.convertRHEVtoOasis(payload=DC,manager=manager)))
	for SD in STORAGEDOMAINS:
	    if SD.type_ != 'data':
		continue
	    sd_oasis = g.oasis.Storage.convertRHEVtoOasis(payload=SD,manager=manager)
	    storage.append({ 'name':sd_oasis['storagePoolName'], 'size_gb':int(sd_oasis['storagePoolSize']), 'free_gb':int(sd_oasis['storagePoolFreeSpace'])})
	   
    except Exception as e:
        current_app.logger.exception('EXCEPTION processing storage domain data for cluster %s' % cluname)
        return Response(json.dumps({'object':'OASIS','exception':str(e)}), status=400,mimetype='application/json')

    # cache the storage domain data
    try:
            g.redis.set('oasis:rhev:storagepools:%s:%s:%s' % (manager,SD.name,SD.id),json.dumps(sd_oasis))
    except Exception as e:
        current_app.logger.exception('EXCEPTION caching RHEV objects!') 

    # return a good response - phew!
    return Response(json.dumps({"storage":storage}),status=200,mimetype='application/json')
