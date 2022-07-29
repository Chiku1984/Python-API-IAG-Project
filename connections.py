from flask import current_app, g
import pickle
import ast
import json
import redis
import requests
import ovirtdata

from ba_rapi.RHEV import RHEV as rhev3
from ovirt4rpyc import API as rhev4

class REDIShelper(object):
    def __init__(self,host='localhost',port=6379,db=0):
	self.host = host
	self.port = port
	self.db = db
	self.redis = redis.Redis(host=host,port=port,db=db)

    def exists(self,key):
        return self.redis.exists(key)

    def set(self,key,value):
	return self.redis.set(key,value)

    def get(self,key):
	return self.redis.get(key)

    def delete(self,key):
	return self.redis.delete(key)

    def keys(self,pattern):
	return self.redis.keys(pattern)

    def keysUnique(self,pattern):
	keys = self.keys(pattern)
	if len(keys) > 1:
            raise Exception, "Multiple keys match pattern %s" % pattern
        if len(keys) == 0:
            raise ValueError, "Cannot find any keys matching %s" % pattern

	return keys[0]

    def getByName(self,key,name):
	return self.get(self.keysUnique("%s:*:%s:*" % (key,name)))

    def getById(self,key,id):
	return self.get(self.keysUnique("%s:*:*:%s" % (key,id)))

    def deleteByName(self,key,name):
	return self.delete(self.keysUnique("%s:*:%s:*" % (key,name)))

    def deleteById(self,key,id):
	return self.delete(self.keysUnique("%s:*:*:%s" % (key,id)))


class RHEVhelper(object):
    def __init__(self):
        self.ovirt_version = None
        self.username = current_app.config['RHEV_USER']
        self.password = current_app.config['RHEV_PASSWORD']


    def __getFormatter(self,manager):
	version = self.__getOvirtVersion(name=manager)

	if version == '3':
	    return ovirtdata.Ovirt3DataFormatter(manager)
	else:
	    return ovirtdata.Ovirt4DataFormatter(manager)


    def __getOvirtVersion(self,url=None,name=None):
        if not url and not name:
            raise Exception, 'One of url or name must be supplied'

        if not url:
            url = 'https://%s/ovirt-engine/api' % name

	print "Using URL %s" % url

        try:
            resp = requests.get(
                        url,
                        headers={'accept':'application/json'},
                        auth=(self.username,self.password),
                        verify=False)
            resp_json = resp.json()

	    print "RESP JSON : %s" % resp_json
        except Exception as e:
            print str(e)
            raise Exception('Unable to connect to ovirt api %s' % url)

        try:
	    print "Version of API:"
	    print resp_json['product_info']['version']['major']
            return resp_json['product_info']['version']['major']
        except:
            raise Exception('Unable to determine API version')


    def __cacheAPI(self,managername,api):
	r = redis.Redis(host='localhost',port=6379,db=0)
	return r.set('rhev:apis:%s' % managername,pickle.dumps(api))


    def __getAPIFromCache(self,managername):
	r = redis.Redis(host='localhost',port=6379,db=0)
	return pickle.loads(r.get('rhev:apis:%s' % managername))
	 

    def initAPI(self,name):
	if not hasattr(g, 'redis'):
	    raise Exception, "No redis session initialised!"

	if not g.redis.exists("oasis:rhev:managers:%s" % name):
	    print "Cannot find details of RHEV Manager %s in Redis" % name
	    raise Exception, "oasis:rhev:managers:%s" % name

	managerobject = ast.literal_eval(g.redis.get("oasis:rhev:managers:%s" % name))
	managerURL = managerobject['managerUrl']

        #
        # Determine which version of the API that we're dealing with
        #

        if not self.ovirt_version:
            self.ovirt_version = self.__getOvirtVersion(url=managerURL)

        if self.ovirt_version == '3':
            api = rhev3(url=managerURL,
                        username=self.username,
                        password=self.password)
                        #ca_file="%s/%s.pem" % (current_app.config['CERTS_DIR'],name))

	    #g.redis.set("rhev:apis:%s" % name,pickle.dumps(api))
	    self.__cacheAPI(name,api)
        else:
            api = rhev4(url=managerURL,
                        username=self.username,
                        password=self.password)

	return api


    def cacheVM(self,vm,clusterName=None,deleteExisting=True):
	if not hasattr(g, 'redis'):
	    raise Exception, "No redis session initialised!"

	vmname = vm.name
	vmid   = vm.id
	if clusterName:
	    manager = self.getManagerNameFromCache(clusterName)
	else:
	    manager = self.getManagerNameFromCache(vmname)

	if deleteExisting:
	    try:
		for key in g.redis.keys("oasis:rhev:vms:*:%s:*" % vmname):
		    g.redis.delete(key)
	    except:
		pass

	formatter = self.__getFormatter(manager)

	print "Caching %s" % json.dumps(formatter.format_vm(vm))

        g.redis.set("oasis:rhev:vms:%s:%s:%s" % (manager,vmname,vmid),json.dumps(formatter.format_vm(vm)))

	return True


    def cacheHost(self,host):
        if not hasattr(g, 'redis'):
            raise Exception, "No redis session initialised!"

        if not g.oasis:
            raise Exception, "No oasis session initialised!"

        hostname = host.name
        hostid   = host.id
        manager = self.getManagerNameFromCache(hostname)

        g.redis.set("oasis:rhev:hosts:%s:%s:%s" % (manager,hostname,hostid),json.dumps(g.oasis.Host.convertRHEVtoOasis(payload=host,manager=manager)))

        return True


    def getManagerNameFromCache(self,name):
	if not hasattr(g, 'redis'):
	    raise Exception, "No redis session initialised!"

	keys = g.redis.keys("oasis:rhev:*:*:%s:*" % name)

	if not keys:
	    raise ValueError, "%s not found in cache" % name
	
	if len(keys) > 1:
	    raise ValueError, "Name %s is cached multiple times - huh?"

	try:
	    cachedObject = ast.literal_eval(g.redis.get(keys[0]))
	except:
	    raise Exception, str(keys[0])

	if 'managerName' in cachedObject:
	    return cachedObject['managerName']
	
	raise ValueError, "No RHEV manager specified for %s object!" % name


    def getVMFromCache(self,vmname):
	if not hasattr(g, 'redis'):
	    raise Exception, "No redis session initialised!"

	keys = g.redis.keys("oasis:rhev:vms:*:%s:*" % vmname)

	if not keys:
	    return None
	
	if len(keys) > 1:
	    raise ValueError, "Name %s is cached multiple times - huh?"

	try:
	    cachedObject = ast.literal_eval(g.redis.get(keys[0]))
	except:
	    raise Exception, str(keys[0])

	return cachedObject


    def getAPI(self,name):
	print "Getting API session"
	try:
	    manager = self.getManagerNameFromCache(name)
	except Exception as e:
	    raise Exception, "Unable to determine RHEV manager for %s. %s" % (name,str(e))
	
	if not hasattr(g, 'redis'):
	    raise Exception, "No redis session initialised!"

	if not g.redis.exists("rhev:apis:%s" % manager):
	    try:
		print "Initialising API session"
		rhevapi = self.initAPI(manager)
	    except Exception as e:
		raise Exception, "Cannot initialise API session for %s : %s" % (manager,str(e))
	else:
	    #rhevapi = pickle.loads(g.redis.get("rhev:apis:%s" % manager))
	    rhevapi = self.__getAPIFromCache(manager)

	    if not rhevapi.test():
		if not rhevapi.initialise():
		    raise Exception, "Unable to establish API session with %s" % manager
	        else:
		    #g.redis.set("rhev:apis:%s" % manager,pickle.dumps(rhevapi))
		    self.__cacheAPI(manager,rhevapi)
	
	return rhevapi


    def getVM(self,vmname):
	if not hasattr(g, 'rhevapi'):
	     g.rhevapi = self.getAPI(vmname)

	VM = g.rhevapi.VM.list(vmname)

	self.cacheVM(VM)
        return VM


    def getHost(self,hostname):
        if not hasattr(g, 'rhevapi'):
             g.rhevapi = self.getAPI(hostname)

        HOST = g.rhevapi.Host.list(hostname)

        if len(HOST) != 1:
            raise Exception, "Multiple Hosts matching name %s" % hostname

        self.cacheHost(HOST[0])
        return HOST[0]
