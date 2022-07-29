import json

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..helpers import HOSTGROUPhelper

blueprint = Blueprint('hostgroups', __name__, url_prefix='/hostgroups')

@blueprint.before_request
def initialise():
    g.hostgroup  = HOSTGROUPhelper(uri=current_app.config['LDAP_URI'],sid=current_app.config['LDAP_SID'],password=current_app.config['LDAP_PASSWD'])


@blueprint.route('', methods=['GET'])
@requires_auth
def list():
    try:
	host = request.args.get('host', None)

	# return only those hostgroups for the specified host
	if host:
	    current_app.logger.info('Listing Hostgroups for host %s' % host)
	    hostgroups = g.hostgroup.getHostHostgroups(host)
	else:
	    current_app.logger.info('Listing all Hostgroups')
	    hostgroups = g.hostgroup.getHostgroups()
    except Exception as e:
	current_app.logger.exception('Exception listing Hostgroups')
	return Response(json.dumps({'object':'LDAP','exception':str(e)}), status=500, mimetype='application/json')

    return Response(json.dumps({'hostgroups':hostgroups}), status=200, mimetype='application/json')


@blueprint.route('/<hostgroup>', methods=['GET'])
@requires_auth
def listHostgroup(hostgroup):
    try:
	current_app.logger.info('Listing host in Hostgroup %s' % hostgroup)
	hosts = g.hostgroup.getHostgroupHosts(hostgroup)
    except Exception as e:
	current_app.logger.exception("Exception listing hosts from %s hostgroup" % hostgroup)
	return Response(json.dumps({'error':str(e)}),status=404)

    return Response(json.dumps({'hosts':hosts}), status=200, mimetype='application/json')


@blueprint.route('/<hostgroup>', methods=['PUT'])
@requires_auth
def add(hostgroup):
    try:
	if 'hosts' not in request.json:
	    raise ValueError, "No hosts specified in input JSON!"

	hosts = request.json['hosts']

	if type(hosts).__name__ != 'list':
	    hosts = [hosts]

	g.hostgroup.addHostsToHostgroup(hosts,hostgroup)
    except Exception as e:
	current_app.logger.exception("Exception adding hosts to %s Hostgroup" % hostgroup)
	return Response(json.dumps({'object':'LDAP','exception':str(e)}), status=500, mimetype='application/json')

    return Response(status=201)


@blueprint.route('/<hostgroup>/<host>', methods=['DELETE'])
@requires_auth
def delete(hostgroup,host):
    try:
	current_app.logger.info("Removing %s from Hostgroup %s" % (host,hostgroup))
	g.hostgroup.delHostsFromHostgroup([host],hostgroup)
    except Exception as e:
	current_app.logger.exception("Exception removing %s from hostgroup %s" % (host,hostgroup))
	return Response(json.dumps({'object':'LDAP','exception':str(e)}), status=500, mimetype='application/json')

    return Response(status=200)
