import json, re
import redis

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth

blueprint = Blueprint('oasis', __name__, url_prefix='/oasis')

from ba_rapi.Oasis import Oasis

@blueprint.before_request
def initialise():
    g.oasis = Oasis(baseurl=current_app.config['OASIS_URL'],apikey=current_app.config['OASIS_APIKEY'])


def createFIQL(args={}):
    print args
    FIQL = ''

    for k,v in args.items():
	if FIQL:
	    FIQL = FIQL + ';'

	FIQL = FIQL + '%s==%s' % (k,v)

    return FIQL


@blueprint.route('/<view>', methods=['GET'])
@requires_auth
def get(view):
    # process request JSON
    try:
	current_app.logger.info('Processing GET request for view %s' % view)

	resp = g.oasis.get(view=view,fiql=createFIQL(request.args))
	resp.raise_for_status()
    except Exception as e:
	current_app.logger.exception('EXCEPTION GETTING view %s' % view)
	current_app.logger.exception(str(e))

    return Response(json.dumps(resp.json()),status=resp.status_code,mimetype='application/json')


@blueprint.route('/<view>/<id>', methods=['GET'])
@requires_auth
def get(view,id):
    # process request JSON
    try:
	current_app.logger.info('Processing GET request for view %s' % view)

	#primary_key = 

	resp = g.oasis.get(view=view,fiql=createFIQL(request.args))
	resp.raise_for_status()
    except Exception as e:
	current_app.logger.exception('EXCEPTION GETTING view %s' % view)
	current_app.logger.exception(str(e))

    return Response(json.dumps(resp.json()),status=resp.status_code,mimetype='application/json')



