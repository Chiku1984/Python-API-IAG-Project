import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

blueprint = Blueprint('vnics', __name__, url_prefix='/vms/<vmname>/nics')

@blueprint.before_request
def initialise():
    g.redis = REDIShelper(host=current_app.config['REDIS_HOST'],
                          port=current_app.config['REDIS_PORT'],
                          db=current_app.config['REDIS_DB'])
    g.rhev  = RHEVhelper()

@blueprint.route('', methods=['GET'])
@requires_auth
def display(vmname):
    try:
	current_app.logger.info('Processing NIC list request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
	vnics = g.rhevapi.VM.listNICs(vmname)

	jsarray = []
	for vnic in vnics:
	    nicjson = {}
            nicjson['name'] = vnic.name
            nicjson['mac']  = vnic.mac.address
            if vnic.network:
                nicjson['network'] = g.rhevapi.Network.list(vnic.network.id).name
	    elif vnic.vnic_profile:
		nicjson['network'] = g.rhevapi.Network.list(vnic.vnic_profile.id).name

            jsarray.append(nicjson)

        js = { "nics":jsarray }

        return Response(json.dumps(js),status=200,mimetype='application/json')

    except Exception as e:
	current_app.logger.exception('EXCEPTION displaying %s NICS' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=404,mimetype='application/json')


@blueprint.route('', methods=['PUT'])
@requires_auth
def update(vmname):
    try:
	current_app.logger.info('Updating VM %s NICs' % vmname)
        current_app.logger.debug('Request JSON : %s' % request.json)
	if 'nics' not in request.json:
	    raise ValueError, 'No nics specified in input json'

	g.rhevapi = g.rhev.getAPI(vmname)
	g.rhevapi.VM.updateNICs(nics=request.json['nics'],vmName=vmname)

	return Response(status=200)

    except Exception as e:
	current_app.logger.exception('EXCEPTION updating VM %s NICs' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=400,mimetype='application/json')
