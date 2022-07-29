import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

from ba_rapi.Oasis import Oasis

blueprint = Blueprint('storage', __name__, url_prefix='/storage')

@blueprint.before_request
def initialise():
    g.oasis = Oasis(baseurl='http://esmapi-dev.baplc.com/oasis/appl',apikey='fad84f06-97d7-4a63-8433-d5abf6f3ff67')
    g.redis = REDIShelper(host=current_app.config['REDIS_HOST'],
                          port=current_app.config['REDIS_PORT'],
                          db=current_app.config['REDIS_DB'])
    g.rhev  = RHEVhelper()

@blueprint.route('', methods=['GET'])
@requires_auth
def getStorage():
    # process the arguments
    try:
	current_app.logger.info('Processing arguments for storage request')
        cluname = request.args.get('cluster',None)
	if not cluname:
	    raise Exception, 'A cluster argument must be specified'
	storage_type = request.args.get('type',None)
	if storage_type:
	    if storage_type not in [ 'XIV', 'SSD' ]:
		raise Exception, 'Supported types are XIV or SSD'
    except Exception as e:
	current_app.logger.exception('EXCEPTION: %s' % str(e))
        return Response(json.dumps({'object':'RHEV','exception':str(e)}), status=400,mimetype='application/json')

    try:
	current_app.logger.info('Processing request for storagedomains for cluster %s')
	g.rhevapi = g.rhev.getAPI(cluname)
	DC = g.rhevapi.Cluster.getDatacenter(cluname) 
        STORAGEDOMAINS = g.rhevapi.DataCenter.getStorageDomains(DC.name,'data')
    except NameError as e:
 	error = 'Unknown cluster name %s' % cluname
        current_app.logger.exception('EXCEPTION: %s' % error)
	return Response(json.dumps({'object':'RHEV','exception':error}), status=404,mimetype='application/json')
    except Exception as e:
	current_app.logger.exception('EXCEPTION retrieving storage domains for cluster %s' % cluname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}), status=400,mimetype='application/json')

    # cache the storage domain output
    # useful thing to do, as we have gone to the trouble of retrieving it
    try:
	manager = g.rhev.getManagerNameFromCache(cluname)
	rediskey = 'oasis:rhev:datacentres:%s:%s:%s' % (manager,DC.name,DC.id)
	g.redis.set(rediskey,json.dumps(g.oasis.Datacentre.convertRHEVtoOasis(payload=DC,manager=manager)))
	for SD in STORAGEDOMAINS:
	    sd_oasis = g.oasis.Storage.convertRHEVtoOasis(payload=SD,manager=manager)
            g.redis.set('oasis:rhev:storagepools:%s:%s:%s' % (manager,SD.name,SD.id),json.dumps(sd_oasis))
    except Exception as e:
        current_app.logger.exception('EXCEPTION caching storagedomain objects!') 

    # a list of storage domains that match the specified type
    matching_storage_domains = []

    # pick out those storage domains with disks of the specified type
    if storage_type:
        vendors = {
	    'XIV': 'IBM',
	    'SSD': 'PURE'
	}

        for SD in STORAGEDOMAINS:
	    try:
		disk1_vendor = SD.storage.volume_group.logical_unit[0].vendor_id
		if disk1_vendor == vendors[storage_type]:
		    matching_storage_domains.append(SD)
	    except Exception as e:
		current_app.logger.exception('EXCEPTION: Cannot determine vendor id of StorageDomain %s' % SD.name)

    # all storage domains match if no type is specified
    else:
        matching_storage_domains = STORAGEDOMAINS

    # return a 404 if no matching storage domains are discovered
    if not matching_storage_domains:
	error = 'No matching storage domains for cluster %s' % cluname
	return Response(json.dumps({'object':'RHEV','exception':error}), status=404,mimetype='application/json')

    # get the name of the matching storage domain with the most available space
    try:
	storage_domain = sorted(matching_storage_domains,key=lambda x: x.available, reverse=True)[0]
	sd_name = storage_domain.name
    except Exception as e:
	current_app.logger.exception('EXCEPTION: Cannot determine storage domain name for cluster %s' % cluname)
    
    # return a good response - phew!
    return Response(json.dumps({"storage_domain":sd_name}),status=200,mimetype='application/json')
