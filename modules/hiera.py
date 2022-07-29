import json
import jsonschema
from redis import Redis
import re

from flask import Blueprint, request, Response, current_app, g
from ..decorators import requires_auth
from ..connections import RHEVhelper, REDIShelper

blueprint = Blueprint('hiera', __name__, url_prefix = '/hiera/<hierarchy>')

def validateHierarchy(hierarchy):
    """Raise an exception if the supplied hierarchy does not appear to be
    a hostname.
    """
    
    for x in current_app.config['HIERA_BLACKLIST']:
	if re.match(x, hierarchy):
	    error = 'FORBIDDEN: Cannot modify entries for hierarchy %s' % hierarchy
	    current_app.logger.debug(error)
	    raise Exception, error

	    
@blueprint.before_request
def initialise():
    """Establish a connection to our hiera Redis host for each request"""
    
    g.redis = Redis(host = current_app.config['HIERA_REDIS_HOST'],
                    port = 6379, db = 0)


@blueprint.route('/filesystems', methods = ['GET'])
@requires_auth
def get_hiera_filesystems(hierarchy):
    try:
	redis_key = '%s:FILESYSTEMS' % hierarchy
	current_app.logger.info('Attempting to return value for Redis key %s' \
                                % redis_key)

	result = g.redis.get(redis_key)

	# return a 404 if no key of that name exists
	if not result:
	    error = 'Redis key %s does not exist' % redis_key
	    current_app.logger.debug(error)
	    return Response(json.dumps({'object': 'HIERA','exception': error}),
                            status = 404, mimetype = 'application/json')

	# return a JSON representation of the filesystems definition
	current_app.logger.info('Value of Redis key %s is %s' % (redis_key, result))
	return Response(json.loads(json.dumps(result)),
                        status = 200, mimetype = 'application/json')

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA','exception': str(e)}),
                        status = 500, mimetype = 'application/json')


@blueprint.route('/filesystems', methods = ['POST'])
@requires_auth
def set_hiera_filesystems(hierarchy):
    try:
	current_app.logger.info(
            'Processing request to set Hiera filesystem definition for %s' \
            % hierarchy)

	# reject requests to blacklisted hierarchies
	try:
	    validateHierarchy(hierarchy)
	except Exception as e:
	    return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                            status = 403, mimetype = 'application/json')

	redis_key = '%s:FILESYSTEMS' % hierarchy
	current_app.logger.debug('Hiera Redis key is %s' % redis_key)

	request_json = request.json
	current_app.logger.debug("Request JSON : %s" % request_json)

	# validate the JSON
	current_app.logger.info('Validating request JSON')
	jsonschema.validate(request_json, {"$ref": "file://%s#/hiera/filesystems" \
                                           % current_app.config['SCHEMAS']})

	# check to see if the Redis key has an existing value - log it if it does
	current_value = g.redis.get(redis_key)
	if not current_value:
	    current_app.logger.debug('Hiera Redis key %s is not currently set' \
                                     % redis_key)
	else:
	    current_app.logger.debug(
                'Hiera Redis key %s contains the following value: %s'\
                % (redis_key, current_value))

	if g.redis.set(redis_key, json.dumps(request_json)):
	    current_app.logger.info(
                'Successfully set Hiera Redis key %s' % redis_key)
	    return Response(status = 201)
	else:
            error = 'Unknown error setting Redis key %s' % redis_key
	    raise Exception(error)
	    current_app.logger.debug(error)

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA','exception': str(e)}),
			status = 500, mimetype = 'application/json')


@blueprint.route('/filesystems', methods = ['DELETE'])
@requires_auth
def delete_hiera_filesystems(hierarchy):
    try:
	current_app.logger.info(
            'Processing request to delete Hiera filesystem definition for %s' \
            % hierarchy)

	# reject requests to blacklisted hierarchies
	try:
	    validateHierarchy(hierarchy)
	except Exception as e:
	    return Response(json.dumps({'object': 'HIERA','exception' :str(e)}),
                            status = 403, mimetype = 'application/json')

	redis_key = '%s:FILESYSTEMS' % hierarchy
	current_app.logger.debug('Hiera Redis key is %s' % redis_key)

	# check to see if the Redis key has an existing value - log it if it does
	current_value = g.redis.get(redis_key)
	if not current_value:
	    error = 'Redis key %s does not exist' % redis_key
	    current_app.logger.debug(error)
	    return Response(json.dumps({'object': 'HIERA','exception': error}),
                            status = 404, mimetype = 'application/json')
	else:
	    current_app.logger.debug(
                'Hiera Redis key %s contains the following value: %s' \
                % (redis_key,current_value))

	if g.redis.delete(redis_key):
	    current_app.logger.info(
                'Successfully deleted Hiera Redis key %s' % redis_key)
	    return Response(status = 200)
	else:
            error = 'Unknown error deleting Redis key %s' % redis_key
            current_app.logger.debug(error)
	    raise Exception(error)

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA','exception': str(e)}),
			status = 500, mimetype = 'application/json')


@blueprint.route('/packages', methods = ['GET'])
@requires_auth
def get_hiera_packages(hierarchy):
    try:
	redis_key = '%s:yum::PACKAGES' % hierarchy
	current_app.logger.info('Attempting to return value for Redis key %s' \
                                % redis_key)

	result = g.redis.smembers(redis_key)

	# return a 404 if no key of that name exists
	if not result:
	    error = 'Redis key %s does not exist' % redis_key
	    current_app.logger.debug(error)
	    return Response(json.dumps({'object': 'HIERA', 'exception': error}),
                            status = 404, mimetype = 'application/json')

	# return a JSON representation of the filesystems definition
	current_app.logger.info('Value of Redis key %s is %s' \
                                % (redis_key, result))
	return Response(json.dumps(list(result)),status = 200,
                        mimetype = 'application/json')

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')


@blueprint.route('/packages', methods = ['POST'])
@requires_auth
def add_hiera_packages(hierarchy):
    try:
	current_app.logger.info(
            'Processing request to add packages to %s hierarchy' % hierarchy)

	# reject requests to blacklisted hierarchies
	try:
	    validateHierarchy(hierarchy)
	except Exception as e:
	    return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                            status = 403, mimetype = 'application/json')

	redis_key = '%s:yum::PACKAGES' % hierarchy
	current_app.logger.debug('Hiera Redis key is %s' % redis_key)

	request_json = request.json
	current_app.logger.debug('Request JSON : %s' % request_json)

	# validate the JSON
	current_app.logger.info('Validating request JSON')
	jsonschema.validate(request_json, {"$ref": "file://%s#/hiera/packages" \
                                           % current_app.config['SCHEMAS']})

	# attempt to add the supplied packages to the hierarchy
	for package in request_json:
	    g.redis.sadd(redis_key,package)

	packages = g.redis.smembers(redis_key)
	if set(request_json).issubset(packages):
	    current_app.logger.info('Successfully added %s to Redis key %s' \
                                    % (request_json, redis_key))
	    return Response(status = 201)
	else:
	    error = 'Unknown error adding %s to Redis key %s' \
                    % (request_json, redis_key)
	    current_app.logger.debug(error)
	    raise Exception(error)

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
			status = 500, mimetype = 'application/json')


@blueprint.route('/packages/<package>', methods = ['DELETE'])
@requires_auth
def delete_hiera_package(hierarchy,package):
    try:
	current_app.logger.info(
            'Processing request to add packages to %s hierarchy' % hierarchy)

	# reject requests to blacklisted hierarchies
	try:
	    validateHierarchy(hierarchy)
	except Exception as e:
	    return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                            status = 403, mimetype = 'application/json')

	redis_key = '%s:yum::PACKAGES' % hierarchy
	current_app.logger.debug('Hiera Redis key is %s' % redis_key)

	packages = g.redis.smembers(redis_key)
	if package not in packages:
	    error = 'Redis key %s does not exist' % redis_key
            current_app.logger.debug(error)
            return Response(json.dumps({'object': 'HIERA', 'exception': error}),
                            status = 404, mimetype = 'application/json')
	
	if g.redis.srem(redis_key, package):
	    return Response(status = 200)
	else:
	    error = 'Unknown error deleting %s from Redis key %s' \
                    % (request_json, redis_key)
	    current_app.logger.debug(error)
	    raise Exception(error)

    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA','exception': str(e)}),
	                status = 500, mimetype = 'application/json')


def get_oracle_installs(key):
    """Returns a list of Oracle version strings contained within the supplied
    Redis key. This function expects the key to contain a serialized JSON
    two-level hash:

    {$oracle_home: {'version': $oracle_version}}

    A list of unique Oracle version strings is returned.
    """
    result = g.redis.get(key)

    # return an empty list if the supplied key does not exist
    if not result:
	return []

    current_app.logger.debug('Value of Redis key %s is %s' % (key,result))

    # create a set of oracle versions - the set ensures that the versions are unique
    result_set = set([x.get('version', None) for x in json.loads(result).values()])

    return list(result_set)


def get_oracle_versions(type, hierarchy):
    result = get_oracle_installs('%s:oracle::%s::installs' \
                                 % (hierarchy, type))

    # return a 404 if no key of that name exists
    if not result:
        error = 'No Oracle %ss defined for %s' % (type, hierarchy)
	current_app.logger.debug(error)
	return Response(json.dumps({'object': 'HIERA', 'exception': error}),
                        status = 404, mimetype = 'application/json')

    return Response(json.dumps(result), status = 200,
                    mimetype = 'application/json')

    
def add_oracle_versions(type, hierarchy, request_json):
        # the two valid types are 'database' and 'client'
        # a type-dependent version suffix is required
        suffixes = {
            'database': '_DB-',
            'client' : '_CL-'
        }

        # if the supplied type is not in the suffixes dictionary
        # then it must be invalid
        try:
            suffix = suffixes[type]
        except KeyError:
            error = 'Type must be one of "database" or "client"'
            raise Exception(error)

    	current_app.logger.info(
            'Processing request to add Oracle %s installs for %s' \
            % (type, hierarchy))

        # reject requests to blacklisted hierarchies
        try:
            validateHierarchy(hierarchy)
        except Exception as e:
            return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                            status = 403, mimetype = 'application/json')

        key = '%s:oracle::%s::installs' % (hierarchy, type)
        current_app.logger.debug('Hiera Redis key is %s' % key)
        current_app.logger.debug('Request JSON : %s' % request_json)

        # validate the JSON
        current_app.logger.info('Validating request JSON')
        jsonschema.validate(request_json,
                            {"$ref": "file://%s#/hiera/oracle_versions" \
                            % current_app.config['SCHEMAS']})

        # this dictionary holds the JSON-formatted versions data for addition
        # to Redis
	versions = {}

        # populate the versions dictionary
	for version in request_json:
            # we need to determine the oracle home from the version string
	    tokens = version.split('-', 1)
	    oracle_home = ''.join([tokens[0], suffix, tokens[1]])
	    # the oracle home is the top-level key in the versions dict
	    versions[oracle_home] = {'version': version}

        # obtain the current oracle versions
        current_value = g.redis.get(key)

        # we need to merge our specified versions with any existing versions
	if current_value:
	    current_versions = json.loads(current_value)
	    new_versions = current_versions
	    # we only add oracle homes that are not already specified
	    new_versions.update(dict([(k, v) for k, v in versions.iteritems() \
                                      if k not in current_versions.keys()]))
	    
	# no existing definitions exist - just add the specified versions
	else:
	    new_versions = versions

        # update Redis with the encoded oracle versions dict
        if g.redis.set(key, json.dumps(new_versions)):
            current_app.logger.info(
                'Successfully set Hiera Redis key %s' % key)
            return Response(status = 201)
        else:
            error = 'Unknown error setting Redis key %s' % key
            current_app.logger.debug(error)
            raise Exception(error)


def delete_oracle_version(type, hierarchy, version):
    if type not in ['database', 'client']:
        raise Exception('type must be one of "database" or "client"')
    
    key = '%s:oracle::%s::installs' % (hierarchy, type)

    current_app.logger.info(
        'Processing request to remove Oracle DB version %s from %s' \
        % (version, hierarchy))

    # reject requests to blacklisted hierarchies
    try:
        validateHierarchy(hierarchy)
    except Exception as e:
        return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 403, mimetype = 'application/json')
        
    if version not in get_oracle_installs(key):
	error = 'Oracle version %s not present in key %s' % (version, key)
	current_app.logger.debug(error)
	return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
			status = 403, mimetype = 'application/json')

    new_versions = dict((k, v) for k, v in \
                        json.loads(g.redis.get(key)).iteritems() \
                        if v.get('version', None) != version)

    if not new_versions:
	if g.redis.delete(key):
	    return Response(status = 200)
	else:
	    error = 'Unknown error removing Redis key %s' % key
	    current_app.logger.debug(error)
	    raise Exception(error)

    else:
	if g.redis.set(key, json.dumps(new_versions)):
            return Response(status = 200)
        else:
            error = 'Unknown error updating Redis key %s' % key
            current_app.logger.debug(error)
            raise Exception(error)
        
    
@blueprint.route('/oracle/databases', methods = ['GET'])
@requires_auth
def get_hiera_oracle_databases(hierarchy):
    try:
        return get_oracle_versions('database', hierarchy)
        
    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')


@blueprint.route('/oracle/databases', methods = ['POST'])
@requires_auth
def add_hiera_oracle_databases(hierarchy):
    try:
        return add_oracle_versions('database', hierarchy, request.json)
            
    # return an appropriate response if an exception is raised
    except Exception as e:
        return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')	


@blueprint.route('/oracle/databases/<version>', methods = ['DELETE'])
@requires_auth
def delete_hiera_oracle_database(hierarchy, version):
    try:
        return delete_oracle_version('database', hierarchy, version)

    # return an appropriate response if an exception is raised
    except Exception as e:
        return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')


@blueprint.route('/oracle/clients', methods = ['GET'])
@requires_auth
def get_hiera_oracle_clients(hierarchy):
    try:
        return get_oracle_versions('client', hierarchy)
        
    # return an appropriate response if an exception is raised
    except Exception as e:
	return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')


@blueprint.route('/oracle/clients', methods = ['POST'])
@requires_auth
def add_hiera_oracle_clients(hierarchy):
    try:
        return add_oracle_versions('client', hierarchy, request.json)
            
    # return an appropriate response if an exception is raised
    except Exception as e:
        return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')	


@blueprint.route('/oracle/clients/<version>', methods = ['DELETE'])
@requires_auth
def delete_hiera_oracle_client(hierarchy, version):
    try:
        return delete_oracle_version('client', hierarchy, version)

    # return an appropriate response if an exception is raised
    except Exception as e:
        return Response(json.dumps({'object': 'HIERA', 'exception': str(e)}),
                        status = 500, mimetype = 'application/json')
