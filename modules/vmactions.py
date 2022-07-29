import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

blueprint = Blueprint('vmactions', __name__, url_prefix='/vms/<vmname>')

from ba_rapi.RHN import RHN

@blueprint.before_request
def initialise():
    g.redis = REDIShelper(host=current_app.config['REDIS_HOST'],
                          port=current_app.config['REDIS_PORT'],
                          db=current_app.config['REDIS_DB'])
    g.rhev  = RHEVhelper()

@blueprint.teardown_request
def disconnect(exc=None):
    try:
	pass
    except:
	pass


@blueprint.route('/status', methods=['GET'])
@requires_auth
def status(vmname):
    try:
	current_app.logger.info('Processing request for %s status' % vmname)
	VM = g.rhev.getVM(vmname)
	try:
	    vmstatus = VM.status.state
	except:
	    vmstatus = str(VM.status)
	if not vmstatus:
	    raise Exception, "Cannot return status of VM %s" % vmname
	return Response(json.dumps({'status':vmstatus}),status=200,mimetype='application/json')
    except Exception as e:
	current_app.logger.exception('EXCEPTION returning status of VM %s' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/start', methods=['POST'])
@requires_auth
def start(vmname):
    try:
	current_app.logger.info('Processing START request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
	g.rhevapi.VM.start(vmname)
	return Response(status=202)
    except Exception as e:
	current_app.logger.exception('EXCEPTION executing a START on VM %s' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/netboot', methods=['POST'])
@requires_auth
def netboot(vmname):
    try:
	current_app.logger.info('Processing net boot request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)	
	VM = g.rhevapi.VM.list(vmname)
	vmstatus = VM.status.state
	if vmstatus != 'down':
	    error = 'VM %s must be down before initiating a net boot %s' % (vmname,vmstatus)
	    current_app.logger.exception(error)
	    return Response(json.dumps({'object':'RHEV','exception':error}),status=403,mimetype='application/json')

	g.rhevapi.VM.netBoot(vmname)
	return Response(status=202)
    except Exception as e:
	current_app.logger.exception('EXCEPTION executing a net boot on VM %s' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/stop', methods=['POST'])
@requires_auth
def stop(vmname):
    try:
	current_app.logger.info('Processing STOP request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
	g.rhevapi.VM.stop(vmname)
	return Response(status=202)
    except Exception as e:
	current_app.logger.exception('EXCEPTION executing a STOP on VM %s' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')


@blueprint.route('/shutdown', methods=['POST'])
@requires_auth
def shutdown(vmname):
    try:
	current_app.logger.info('Processing SHUTDOWN request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
        g.rhevapi.VM.shutdown(vmname)
        return Response(status=202)
    except Exception as e:
	current_app.logger.exception('EXCEPTION executing a SHUTDOWN on VM %s' % vmname)
        return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=500,mimetype='application/json')
