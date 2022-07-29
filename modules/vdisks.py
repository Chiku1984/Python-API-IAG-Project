import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper

blueprint = Blueprint('vdisks', __name__, url_prefix='/vms/<vmname>/disks')

#
# Helper function to create RAPI json object
# from RHEV VMDisk object
#
def build_disk_json(disk):
   diskjson = {}
   diskjson['name'] = disk.name
   diskjson['size']  = disk.size / (1024*1024*1024)
   diskjson['bootable'] = disk.bootable
   diskjson['status'] = disk.status.state
   diskjson['active'] = disk.active

   return diskjson


@blueprint.before_request
def initialise():
    g.redis = redis.Redis(host='localhost',port=6379,db=0)
    g.rhev  = RHEVhelper()


@blueprint.route('', methods=['GET'])
@requires_auth
def display(vmname):
    try:
	current_app.logger.info('Processing Disk list request for VM %s' % vmname)
	g.rhevapi = g.rhev.getAPI(vmname)
	vdisks = g.rhevapi.VM.listDisks(vmName=vmname)

	jsarray = []
	for vdisk in vdisks:
	    jsarray.append(build_disk_json(vdisk))

        js = { "disks":jsarray }

        return Response(json.dumps(js),status=200,mimetype='application/json')

    except Exception as e:
	current_app.logger.exception('EXCEPTION displaying %s Disks' % vmname)
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=404,mimetype='application/json')


@blueprint.route('/<diskname>', methods=['GET'])
@requires_auth
def display_disk(vmname,diskname):
    try:
	current_app.logger.info('Displaying Disk %s from VM %s' % (diskname,vmname))
	g.rhevapi = g.rhev.getAPI(vmname)
	try:
	    disk = g.rhevapi.VM.listDisks(vmName=vmname,diskName=diskname)
	    if not disk:
		raise ValueError, 'VM %s does not have a disk named %s' % (vmname,diskname)
	except Exception as e:
	    current_app.logger.exception('EXCEPTION : %s' % str(e))
	    return Response(status=404)

        return Response(json.dumps(build_disk_json(disk)),status=200,mimetype='application/json')

    except Exception as e:
	current_app.logger.exception('EXCEPTION : %s' % str(e))
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=404,mimetype='application/json')


@blueprint.route('/<diskname>', methods=['PUT'])
@requires_auth
def update_disk(vmname,diskname):
    try:
	current_app.logger.info('Updating VM Disk %s' % diskname)
        current_app.logger.debug('Request JSON : %s' % request.json)

	g.rhevapi = g.rhev.getAPI(vmname)
	try:
	    disk = g.rhevapi.VM.listDisks(vmName=vmname,diskName=diskname)
            if not disk:
                raise ValueError, 'VM %s does not have a disk named %s' % (vmname,diskname)
        except Exception as e:
            current_app.logger.exception('EXCEPTION : %s' % str(e))
            return Response(status=404)

	g.rhevapi.VM.updateDisk(disk,**request.json)

	return Response(status=202)

    except Exception as e:
	current_app.logger.exception('EXCEPTION : %s' % str(e))
	return Response(json.dumps({'object':'RHEV','exception':str(e)}),status=400,mimetype='application/json')
