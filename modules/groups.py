import json

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..helpers import getentHelper

blueprint = Blueprint('groups', __name__, url_prefix='/groups')

@blueprint.before_request
def initialise():
    g.getent  = getentHelper()


@blueprint.route('/<groupname>', methods=['GET'])
@requires_auth
def listUser(groupname):
    try:
	current_app.logger.info('Listing group %s' % groupname)
	group = g.getent.getGroup(groupname)
    except NameError as n:
        error = 'Exception: %s' % str(n)
	current_app.logger.exception(error)
	return Response(json.dumps({'error':str(n)}),status=404, mimetype='application/json')
    except Exception as e:
	error = 'Exception: %s' % str(e)
	current_app.logger.exception(error)
	return Response(json.dumps({'error':str(e)}),status=400, mimetype='application/json')

    return Response(json.dumps({'group':group}), status=200, mimetype='application/json')
