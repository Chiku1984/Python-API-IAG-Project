import json

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..helpers import getentHelper

blueprint = Blueprint('users', __name__, url_prefix='/users')

@blueprint.before_request
def initialise():
    g.getent  = getentHelper()


@blueprint.route('/<username>', methods=['GET'])
@requires_auth
def listUser(username):
    try:
	current_app.logger.info('Listing user %s' % username)
	user = g.getent.getUser(username)
    except NameError as n:
        error = 'Exception: %s' % str(n)
	current_app.logger.exception(error)
	return Response(json.dumps({'error':str(n)}),status=404, mimetype='application/json')
    except Exception as e:
	current_app.logger.exception("Exception listing user %s" % username)
	return Response(json.dumps({'error':str(e)}),status=400, mimetype='application/json')

    return Response(json.dumps({'user':user}), status=200, mimetype='application/json')
