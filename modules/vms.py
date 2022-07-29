import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

from ba_rapi.Katello import Katello

blueprint = Blueprint('vms', __name__, url_prefix='/vms')

@blueprint.before_request
def initialise():
    g.katello = Katello(url=current_app.config['KATELLO_API'],
	 		username=current_app.config['KATELLO_USER'],
			password=current_app.config['KATELLO_PASSWD'])
    g.redis = REDIShelper(host=current_app.config['REDIS_HOST'],
			  port=current_app.config['REDIS_PORT'],
			  db=current_app.config['REDIS_DB'])
    g.rhev  = RHEVhelper()


@blueprint.route('', methods=['POST'])
@requires_auth
def create():
    # process request JSON
    try:
        current_app.logger.info('Processing request to create a VM')
        rjson = request.json
        current_app.logger.debug("Request JSON : %s" % rjson)

        vmname     = rjson['host']['name']
        domain     = rjson['host']['domain']
        cluname    = rjson['vm']['cluster']

        if 'os' in rjson:
            os_config = rjson['os']
            try:
                os_version = os_config['version']
            except:
                raise Exception("You must specify version in the 'os' section")

            os_type = os_config.get('type',current_app.config['DEFAULT_OS_TYPE'])
            os_arch = os_config.get('arch',current_app.config['DEFAULT_OS_ARCH'])
            os_name = "%s_%s_%s" % (os_type,os_version,os_arch)

            if os_name in current_app.config['OS'].keys():
                pass
            else:
                raise Exception('%s is not a supported OS' % os_name)

            current_app.logger.debug('Retrieving OS configuration settings for version %s' % os_name)

            os_dict = current_app.config['OS'].get(os_name,{})

            # we need to get the VM OS type
            if 'vm_os_type' in os_dict:
                vm_os_type = os_dict['vm_os_type']
                rjson['vm']['os'] = {'type':vm_os_type}
            else:
                raise Exception('Cannot determine VM OS type for OS %s' % os_name)

        else:
            try:
                vm_os_type = rjson['vm']['os']['type']
            except:
                raise Exception('No OS version specified in input JSON!')

            ks_profile = current_app.config['KS'].get(vm_os_type, current_app.config['DEFAULT_KS'])

        if 'foreman' in rjson:
            foreman_params = {
                'name': vmname,
		'domain': domain,
                'hostgroup': rjson['foreman']['hostgrp_name'],
                'capsule': rjson['foreman'].get('capsule_name','yyprdap26a.baplc.com'),
                'location': rjson['foreman'].get('location','BDC'),
                'mac': rjson['foreman']['mac'],
                'subnet': rjson['foreman'].get('subnet',None),
                'ip': rjson['foreman'].get('ip',None)
            }
        else:
            foreman_params = None

        if 'template' in rjson['vm']:
            templateBuild = True
        else:
            templateBuild = False

    except Exception as e:
        current_app.logger.exception('EXCEPTION processing VM creation request')
        return Response(json.dumps({'object':'REQUEST','exception':"Exception raised handing request : %s" % str(e)}),
                                    status=400,mimetype='application/json')

    # connect to RHEV and attempt VM build
    try:
        current_app.logger.info('Creating RHEV VM %s' % vmname)
        g.rhevapi = g.rhev.getAPI(cluname)
        VM = g.rhevapi.VM.create(
                        name = vmname,
                        **rjson['vm']
                )
    except Exception as e:
        current_app.logger.exception('EXCEPTION creating RHEV VM %s' % vmname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),
                                   status=400,mimetype='application/json')

    # cache the VM
    try:
        current_app.logger.info('Caching VM %s' % vmname)
        g.rhev.cacheVM(vm=VM,clusterName=cluname)
    except Exception as e:
        current_app.logger.exception('EXCEPTION caching VM in redis!')

    # get MAC address from RHEV
    try:
        current_app.logger.debug('Retrieving boot interface MAC address for %s from RHEV' % vmname)
        vm_mac = g.rhevapi.VM.getMACAddress(vmname)
        current_app.logger.debug('Boot interface MAC address for %s is %s' % (vmname,vm_mac))
    except Exception as e:
        current_app.logger.exception(str(e))
        print Response(json.dumps({'object':'RHEV','exception':str(e)}),
                                  status=404,mimetype='application/json')

    # configure the foreman host entry
    if foreman_params:
        try:
	    fqdn = '%s.%s' % (vmname,domain)
            current_app.logger.info('Processing foreman entry for %s' % fqdn)

            # create a new entry if one does not already exist ...
            if not g.katello.Hosts.exists(fqdn):
                current_app.logger.debug('Adding %s to foreman in hostgroup %s' % (fqdn,foreman_params['hostgroup']))
                g.katello.Hosts.addBareMetal(**foreman_params)

            # ... set the hostgroup if the foreman entry does exist
            else:
                current_app.logger.debug('%s already defined! Setting hostgroup to %s' % (fqdn,foreman_params['hostgroup']))
                g.katello.Hosts.setHostgroup(host=fqdn,hostgroupName=foreman_params['hostgroup'])

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


@blueprint.route('/<vmname>',methods=['PUT'])
@requires_auth
def update(vmname):
    # process request JSON
    try:
	current_app.logger.info('Processing request to update a VM')
	request_json = request.json
	current_app.logger.debug("Request JSON : %s" % request_json)

    except Exception as e:
	err='EXCEPTION processing request: %s' % str(e)
	current_app.logger.exception(err)
	return Response(json.dumps({'object':'REQUEST','exception':err}),status=400,mimetype='application/json')

    try:
	current_app.logger.info('Updating RHEV VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
	VM = g.rhevapi.VM.update(
			vmName = vmname,
			**request_json
		)

    except Exception as e:
	err='EXCEPTION updating VM %s : %s' % (vmname,str(e))
	current_app.logger.exception(err)
	return Response(json.dumps({'object':'RHEV','exception':err}),status=400,mimetype='application/json')

    # return a good response
    return Response(status=200)


@blueprint.route('/<vmname>', methods=['GET'])
@requires_auth
def get(vmname):
    try:
	vmcache = g.rhev.getVMFromCache(vmname)
	if not vmcache:
	    return Response(status=404)
	else:
	    return Response(json.dumps(vmcache),status=200,mimetype='application/json')
    except Exception as e:
	current_app.logger.exception('EXCEPTION retrieving %s from cache' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),
			status=500,mimetype='application/json')


@blueprint.route('/<vmname>', methods=['DELETE'])
@requires_auth
def delete(vmname):
    # remove the Foreman host definition
    try:
	if re.search('[A-Za-z0-9]*\.',vmname):
            foreman_name = vmname
        else:
            foreman_name = vmname + '.baplc.com'

        g.katello.Hosts.delete(foreman_name)
    except Exception as e:
	current_app.logger.exception('EXCEPTION removing foreman host %s' % foreman_name)

    # get RHEV api session and attempt VM deletion
    try:
	current_app.logger.debug('Retrieving RHEV API session')
	g.rhevapi = g.rhev.getAPI(vmname)
	current_app.logger.debug('Deleting RHEV VM %s' % vmname)
	g.rhevapi.VM.delete(name=vmname)
    except Exception as e:
	current_app.logger.exception('EXCEPTION deleting RHEV VM %s' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),
                        status=500,mimetype='application/json')

    # remove the VM from cache
    try:
	current_app.logger.debug('Removing cached entry for VM %s' % vmname)
	g.redis.deleteByName('oasis:rhev:vms', vmname)
    except Exception as e:
	current_app.logger.exception()
	return Response(json.dumps({'object':'CACHE','exception':str(e)}),
			status=500,mimetype='application/json')

    # return a good response - phew!
    return Response(status=200)
