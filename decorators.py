import json
from flask import request, current_app, Response
from functools import wraps

def check_auth(username, password):
    return username == current_app.config['RHEV_USER'] and password == current_app.config['RHEV_PASSWORD']


def authenticate():
    resp = { 'message' : 'You must authenticate with valid credentials' }
    return Response(json.dumps(resp),status=401,headers={'WWW-Authenticate':'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
