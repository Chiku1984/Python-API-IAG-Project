import json
import pymongo

from flask import Blueprint, request, Response, current_app, g

blueprint = Blueprint('rip', __name__, url_prefix = '/rip')

@blueprint.before_request
def initialise():
    g.client = pymongo.MongoClient(current_app.config['MONGO_HOST'],
				   current_app.config['MONGO_PORT'])

@blueprint.route('/<host>', methods = ['GET'])
def get_host_parameters(host):
    try:
	ripparms = g.client.hiera.hosts.find_one({'_id':host})

	if not ripparms:
            return Response(status=404)

	return Response(json.dumps(ripparms), status=200, mimetype='application/json')
    except Exception as e:
	return Response(json.dumps({'object': 'RIP','exception': str(e)}),
                        status = 500, mimetype = 'application/json')
