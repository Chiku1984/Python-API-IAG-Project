import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

blueprint = Blueprint('hosts', __name__, url_prefix='/hosts')

from ba_rapi.Oasis import Oasis

@blueprint.before_request
def initialise():
    g.redis = REDIShelper()
    g.rhev  = RHEVhelper()
    g.oasis = Oasis(baseurl='http://esmapi-dev.baplc.com/oasis/appl',apikey='fad84f06-97d7-4a63-8433-d5abf6f3ff67')


@blueprint.route('', methods=['POST'])
@requires_auth
def create():
    # process request JSON
    try:
	current_app.logger.info('Processing request to create a host')
	request_json = request.json
	current_app.logger.debug("Request JSON : %s" % request_json)

        hostname   = request_json['name']
        cluname    = request_json['cluster']
    except Exception as e:
	current_app.logger.exception('EXCEPTION processing RHEV host installation request')
	return Response(json.dumps({'object':'REQUEST','exception':"Exception raised handing request : %s" % str(e)}),
				    status=400,mimetype='application/json')

    # connect to RHEV and attempt Host build
    try:
	current_app.logger.info('Creating RHEV Host %s' % hostname)
	g.rhevapi = g.rhev.getAPI(cluname)
	HOST = g.rhevapi.Host.install(**request_json)
	current_app.logger.info('Finished RHEV host build!')
    except Exception as e:
	current_app.logger.exception('EXCEPTION creating RHEV Host %s' % hostname)

	# try to remove the failed host
	try:
	    current_app.logger.debug('Removing host %s after installation error' % hostname)
	    g.rhevapi.Host.delete(hostname)
	except Exception as e2:
	    current_app.logger.exception('EXCEPTION removing host %s after installation error' % hostname)
	    current_app.logger.exception(str(e2))

	return Response(json.dumps({'object':'RHEV','exception':str(e)}),
				   status=400,mimetype='application/json')

    # cache the Host
    try:
	current_app.logger.info('Caching RHEV Host %s' % hostname)

	current_app.logger.debug('Retrieving RHEV manager for cluster %s from cache' % cluname)
	manager = g.rhev.getManagerNameFromCache(cluname)
        current_app.logger.debug('RHEV Manager for cluster %s is %s' % (cluname,manager))

        rediskey = 'oasis:rhev:hosts:%s:%s:%s' % (manager,hostname,HOST[0].id)
        current_app.logger.debug('Caching RHEV Host using Redis Key %s' % rediskey)
        g.redis.set(rediskey,json.dumps(g.oasis.Host.convertRHEVtoOasis(payload=HOST,manager=manager)))
    except Exception as e:
        current_app.logger.exception('EXCEPTION caching RHEV Host in redis!')

    # return a good response - phew!
    return Response(status=200)


@blueprint.route('/<hostname>', methods=['DELETE'])
@requires_auth
def delete(hostname):
    try:
        current_app.logger.debug('Retrieving RHEV API session')
        g.rhevapi = g.rhev.getAPI(hostname)
	current_app.logger.debug('Deleting RHEV Host %s' % hostname)
	g.rhevapi.Host.delete(hostname)
    except Exception as e:
        current_app.logger.exception('EXCEPTION deleting RHEV Host %s' % hostname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')

    # remove the Host from cache
    try:
	current_app.logger.debug('Removing cached entry for host %s' % hostname)
        g.redis.deleteByName('oasis:rhev:hosts', hostname)
    except Exception as e:
        current_app.logger.exception()
        return Response(json.dumps({'object':'CACHE','exception':str(e)}),
                        status=500,mimetype='application/json')

    # return a good response - phew!
    return Response(status=200)


@blueprint.route('/<hostname>/networks', methods=['GET'])
@requires_auth
def getNetworks(hostname):
    try:
        current_app.logger.info('Processing request for network details for host %s' % hostname)
        g.rhevapi = g.rhev.getAPI(hostname)
        host_networks = g.rhevapi.Host.listNetworks(hostname)
    except Exception as e:
        current_app.logger.exception('EXCEPTION retrieving network details for RHEV host %s' % hostname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),
                                   status=400,mimetype='application/json')

    networks = []

    for net in host_networks:
        if net.name == 'rhevm':
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


@blueprint.route('/<hostname>/networks', methods=['PUT'])
@requires_auth
def addClusterNetworks(hostname):
    try:
	current_app.logger.info('Adding cluster networks to host %s' % hostname)
	g.rhevapi = g.rhev.getAPI(hostname)
	g.rhevapi.Host.addClusterNetworks(hostname)

    except Exception as e:
	current_app.logger.exception('Exception processing addition of cluster networks to host %s' % hostname)
	return Response(json.dumps({'object':'REQUEST','exception':"Exception raised handling request : %s" % str(e)}))

    return Response(status=200)

 
@blueprint.route('/<hostname>/networks', methods=['POST'])
@requires_auth
def addNetwork(hostname):
    # process request JSON
    try:
        current_app.logger.info('Processing request to add network to host %s' % hostname)
        request_json = request.json
        current_app.logger.debug("Request JSON : %s" % request_json)

        if 'vlanid' not in request_json:
            raise Exception("Request json must contain a 'vlanid' element")

    except Exception as e:
        current_app.logger.exception('Exception processing host network addition')
        return Response(json.dumps({'object':'REQUEST','exception':"Exception raised handling request : %s" % str(e)}),
                                    status=400,mimetype='application/json')

    # connect to RHEV and attempt cluster network addition
    try:
        current_app.logger.info('Adding vlanid %s to host %s' % (request_json['vlanid'],hostname))
        g.rhevapi = g.rhev.getAPI(hostname)

	# we need to know what networks have been configured on the host's cluster firts
	clu_networks = g.rhevapi.Host.listClusterNetworks(hostname)
        
	# we need to retrieve the cluster network object with a matching vlan id
	clu_network = next(( x for x in clu_networks if x.vlan and x.vlan.id == request_json['vlanid'] ), None)

	if not clu_network:
	    current_app.logger.debug('No cluster network with vlan id %s' % request_json['vlanid'])
	    return Response(json.dumps({'object':'RHEV','exception':'VLAN ID %s not configured on cluster' % request_json['vlanid']}),status=404,mimetype='application/json')

	g.rhevapi.Host.addNetwork(hostname = hostname, network = clu_network)

    except Exception as e:
        current_app.logger.exception('EXCEPTION adding vlanid %s to host %s' % (request_json['vlanid'],hostname))
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=400,mimetype='application/json')

    # return a good response
    return Response(status=200)


@blueprint.route('/<hostname>/status', methods=['GET'])
@requires_auth
def status(hostname):
    try:
        current_app.logger.info('Processing request for %s status' % hostname)
        HOST = g.rhev.getHost(hostname)
	hoststatus = HOST.status.state
        if not hoststatus:
            raise Exception, "Cannot return status of Host %s" % hostname
        return Response(json.dumps({'status':hoststatus}),status=202,mimetype='application/json')
    except Exception as e:
        current_app.logger.exception('EXCEPTION returning status of Host %s' % hostname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/<hostname>/activate', methods=['POST'])
@requires_auth
def activate(hostname):
    try:
	current_app.logger.info('Processing ACTIVATE request for Host %s' % hostname)
	HOST = g.rhev.getHost(hostname)
	HOST.activate()
	return Response(status=202)
    except Exception as e:
	current_app.logger.exception('EXCEPTION ACTIVATING Host %s' % hostname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/<hostname>/deactivate', methods=['POST'])
@requires_auth
def deactivate(hostname):
    try:
        current_app.logger.info('Processing DEACTIVATE request for Host %s' % hostname)
        HOST = g.rhev.getHost(hostname)
        HOST.deactivate()
        return Response(status=202)
    except Exception as e:
        current_app.logger.exception('EXCEPTION DEACTIVATING Host %s' % hostname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')
