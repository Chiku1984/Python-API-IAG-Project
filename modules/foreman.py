import json
import re

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper

from ba_rapi.Katello import Katello

blueprint = Blueprint('foreman', __name__, url_prefix='/foreman')

@blueprint.before_request
def initialise():
    g.katello  = Katello(url=current_app.config['KATELLO_API'],
			 username=current_app.config['KATELLO_USER'],
			 password=current_app.config['KATELLO_PASSWD'])

@blueprint.route('', methods=['POST'])
@requires_auth
def create():
    # process request JSON
    try:
        current_app.logger.info('Processing foreman host creation request')
        rjson = request.json
        current_app.logger.debug('Request JSON = %s' % rjson)

        params = {
                'name': rjson['host']['name'],
		'domain': rjson['host']['domain'],
                'hostgroup': rjson['foreman']['hostgrp_name'],
                'capsule': rjson['foreman'].get('capsule_name','yyprdap26a.baplc.com'),
                'location': rjson['foreman'].get('location','BDC'),
                'mac': rjson['foreman']['mac'],
                'subnet': rjson['foreman'].get('subnet',None),
                'ip': rjson['foreman'].get('ip',None)
        }

    except Exception as e:
        current_app.logger.exception('EXCEPTION processing request JSON')
        return Response(json.dumps({'object':'REQUEST','exception':str(e)}),
                                    status=400,mimetype='application/json')

    # configure host in foreman
    try:
	fqdn = '%s.%s' % (params['name'],params['domain'])
        current_app.logger.info('Processing foreman entry for %s' % fqdn)

        # create a new entry if one does not already exist ...
        if not g.katello.Hosts.exists(fqdn):
            current_app.logger.debug('Adding %s to foreman in hostgroup %s' % (fqdn,params['hostgroup']))
            g.katello.Hosts.addBareMetal(**params)

        # ... set the hostgroup if the foreman entry does exist
        else:
            current_app.logger.debug('%s already defined! Setting hostgroup to %s' % (fqdn,params['hostgroup']))
            g.katello.Hosts.setHostgroup(host=fqdn,hostgroupName=params['hostgroup'])

        # add any puppet classes that have been requested
        if 'puppetclasses' in rjson['foreman'] and rjson['foreman']['puppetclasses']:
            puppetclasses = rjson['foreman']['puppetclasses']
            if type(puppetclasses).__name__ != 'list':
                puppetclasses = [puppetclasses]
            for puppetclass in puppetclasses:
                current_app.logger.debug('Adding puppet class %s to foreman host %s' % (puppetclass,fqdn))
                g.katello.Hosts.addPuppetClass(fqdn,puppetclass)

	# add any parameters that have been requested
	parameters = rjson['foreman'].get('parameters',None)
	if parameters:
	    current_app.logger.debug('Adding parameters to foreman host %s' % fqdn)
	    g.katello.Hosts.setParameters(fqdn,parameters)
    except Exception as e:
        current_app.logger.exception('EXCEPTION processing foreman host definition %s' % fqdn)
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}),
                        status=404,mimetype='application/json')

    # return a good response - phew!
    return Response(status=200)


@blueprint.route('/<fqdn>', methods=['DELETE'])
@requires_auth
def delete(fqdn):
    # remove the Foreman host definition
    try:
        if not re.search('[A-Za-z0-9]*\.',fqdn):
            raise Exception, 'You must supply an FQDN not a short hostname'

        g.katello.Hosts.delete(fqdn)
    except Exception as e:
        current_app.logger.exception('EXCEPTION removing foreman host %s' % fqdn)

    return Response(status=200)


@blueprint.route('/<hostname>/parameters', methods=['POST','PUT'])
@requires_auth
def set_parameters(hostname):
    # process request JSON
    try:
        current_app.logger.info('Processing foreman set parameters request for host %s' % hostname)
        rjson = request.json

	if type(rjson).__name__ != 'list':	
	    raise Exception, "Request JSON must be a list of dictionaries"

	for d in rjson:
	    if type(d).__name__ != 'dict':
		raise Exception, "Request JSON must be a list of dictionaries"

	    if not all (k in d for k in ('name','value')):
		raise Exception, "Request JSON parameter definitions require 'name' and 'value' keys"
	    
    except Exception as e:
        current_app.logger.exception('EXCEPTION processing request JSON')
        return Response(json.dumps({'object':'REQUEST','exception':str(e)}), status=400,mimetype='application/json')

    try:
        g.katello.Hosts.setParameters(hostname,rjson)
   
    except Exception as e:
	current_app.logger.exception('EXCEPTION setting parameters for host %s' % hostname)
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')

    return Response(status=201)


@blueprint.route('/<hostname>/parameters', methods=['GET'])
@requires_auth
def get_parameters(hostname):
    host_parameters = []
    hostgroup_parameters = []

    # retrieve the foreman host parameters
    try:
	current_app.logger.info('Retrieving Foreman parameters for host %s' % hostname)

	host = g.katello.Hosts.list(hostname)

	if not host:
	    current_app_logger.debug('Foreman does not contain a system called %s' % hostname)
	    response = json.dumps({'message':"Foreman host definition %s not found!" % hostname})

            return (response,404,{'Content-type':'application/json'})

	host_parameters = g.katello.Hosts.getParameters(hostname)
	current_app.logger.info('HOST PARAMS: %s' % str(host_parameters))
	for x in host_parameters:
	    x.update({'scope':'host'})

    except Exception as e:
	current_app.logger.exception('EXCEPTION getting foreman parameters for host %s' % hostname)
	return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')


    # retrieve any parameters for the host's hostgroup
    try:
	hostgroup_id = host['hostgroup_id']

	# if the host is part of a hostgroup
	if hostgroup_id:
	    hostgroup_parameters = g.katello.Hostgroups.getParameters(hostgroup_id)
	    for x in hostgroup_parameters:
		x.update({'scope':'hostgroup'})

    except Exception as e:
	current_app.logger.exception('EXCEPTION getting foreman parameters for hostgroup %s' % hostgroup_id)
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')


    # merge the host and hostgroup parameters into a single array, favouring host parameters over hostgroup parameters
    # where duplicates exist
    try:
	parameters = host_parameters
	parameters.extend([x for x in hostgroup_parameters if x['name'] not in [y['name'] for y in host_parameters]])

    except Exception as e:
	current_app.logger.exception('EXCEPTION merging foreman hostgroup parameters for host %s' % hostname)
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')
	
    return Response(json.dumps({'parameters':parameters}), status=200, mimetype='application/json')


@blueprint.route('/<hostname>/parameters/<paramname>', methods=['PUT'])
@requires_auth
def set_parameter(hostname,paramname):
    # process request JSON
    try:
        current_app.logger.info('Processing foreman parameter update request')
        request_json = request.json

	if not request_json['value']:
	    raise Exception, "Request JSON must include a value key!"
	    
    except Exception as e:
        current_app.logger.exception('EXCEPTION processing request JSON')
        return Response(json.dumps({'object':'REQUEST','exception':str(e)}), status=400,mimetype='application/json')

    try:
        g.katello.Hosts.setParameter(hostname,paramname,request_json['value'])
   
    except Exception as e:
	current_app.logger.exception('EXCEPTION setting parameter %s for host %s' % (paramname,hostname))
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')

    return Response(status=201)


@blueprint.route('/<hostname>/parameters/<paramname>', methods=['DELETE'])
@requires_auth
def delete_parameter(hostname,paramname):
    try:
	if not g.katello.Hosts.getParameter(hostname,paramname):
	    current_app.logger.debug('Foreman parameter %s does not exist for host %s' % (paramname,hostname))
            return Response(status=404)

	if not g.katello.Hosts.removeParameter(hostname,paramname):
	    raise Exception, 'Unknown error removing parameter %s from host %s' % (paramname,hostname)

    except Exception as e:
	current_app.logger.exception('EXCEPTION removing parameter %s from host %s' % (paramname,hostname))
        return Response(json.dumps({'object':'FOREMAN','exception':str(e)}), status=500, mimetype='application/json')

    return Response(status=200)
