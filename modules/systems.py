import json, re
import redis
from datetime import datetime
from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth

blueprint = Blueprint('systems', __name__, url_prefix='/systems')

from ba_rapi.Katello import Katello

@blueprint.before_request
def initialise():
    g.katello = Katello(url=current_app.config['KATELLO_API'],
			username=current_app.config['KATELLO_USER'],
			password=current_app.config['KATELLO_PASSWD'])


@blueprint.route('/<vmname>',methods=['GET'])
@requires_auth
def systemstatus(vmname):
    (hostname,dot,domain) = vmname.partition('.')
    if not domain:
	domain = 'baplc.com'

    fqdn = '%s.%s' % (hostname,domain)

    try:
	current_app.logger.info('Processing request for %s system details' % vmname)

	rhn_hash = {
		'active':None,
		'up_to_date':None,
		'last_checkin':None,
		'osa_status':None,
		'lock_status':None
	}

	system = g.katello.Systems.getByName(fqdn)

	rhn_hash['last_checkin'] = system.get('checkin_time',None)
	rhn_hash['active'] = g.katello.Systems.isActive(system=system)
	rhn_hash['up_to_date'] = g.katello.Systems.isUptodate(system=system)

    except ValueError as e:
	current_app.logger.exception('Exception getting %s system details' % vmname)
	return Response(json.dumps({'object':'KATELLO','exception':str(e)}),status=404,mimetype='application/json')
    except Exception as e:
	current_app.logger.exception('Exception getting %s system details' % vmname)
	return Response(json.dumps({'object':'KATELLO','exception':str(e)}),status=500,mimetype='application/json')

    try:
	foreman_hash = {
		'environment':None,
		'hostgroup':None,
		'created_at':None,
		'last_report':None,
		'facts':None
	}

	foreman_details = g.katello.Hosts.list(fqdn)

	foreman_hash['environment'] = foreman_details.get('environment_name',None)
	foreman_hash['last_report'] = foreman_details.get('last_report',None)
	foreman_hash['created_at'] = foreman_details.get('installed_at',None)
	foreman_hash['hostgroup'] = foreman_details.get('hostgroup_name',None)
	foreman_hash['facts'] = {}
	try:
	    foreman_hash['facts']['ba_runlevel'] = g.katello.Hosts.getFact(host=fqdn,fact='runlevel')
	except Exception as e:
	    print str(e)
	    pass

    # we don't want to fail if the host is not in Foreman - we can return None instead
    except Exception as e:
	current_app.logger.exception('EXCEPTION retrieving foreman details for %s' % fqdn)
	pass

    js = {"system":{"satellite":rhn_hash,"foreman":foreman_hash}}

    return Response(json.dumps(js),status=200,mimetype='application/json')
