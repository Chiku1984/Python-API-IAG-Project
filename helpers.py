from flask import current_app, g
from subprocess import Popen, PIPE
import pickle
import ast
import json
import redis
import ldap
import re

class getentHelper(object):
    def __init__(self):
        self.command = [ '/usr/local/bin/bagetent', '-a' ]
        self.options = { 'shell':True, 'stdout':PIPE, 'stdin':PIPE }

    def __bagetent(self,database,resource):
	command = self.command
	command.extend([database, resource])
	
        process = Popen(" ".join(command), shell=True, stdout=PIPE, stderr=PIPE)
	stdout_value, stderr_value = process.communicate()
	
	if process.returncode != 0:
	    raise Exception, 'Unknown error looking up %s' % resource

	if stdout_value == "":
	    raise NameError, '%s not found' % resource

	return stdout_value.strip()

    def getUser(self,username):
	return self.__bagetent('passwd',username)

    def getGroup(self,groupname):
	return self.__bagetent('group',groupname)


class HOSTGROUPhelper(object):
    def __init__(self,uri,sid,password):
	self.uri=uri
	self.sid=sid
	self.password=password
	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
	self.l = ldap.initialize(uri)
	self.__bind()


    def __modify(self, dn, attrs):
	if not self.l:
	    return False
	self.l.modify_s(dn, attrs)


    def __search(self, dn, searchFilter, retrieveAttributes):
	result_id = self.l.search(dn, ldap.SCOPE_SUBTREE, searchFilter, retrieveAttributes)
	result_set = []

	while True:
	    result_type, result_data = self.l.result(result_id, 0)
	    if (result_data == []):
		break
	    else:
		if result_type == ldap.RES_SEARCH_ENTRY:
		    for x in result_data:
			for y in x[1].keys():
		            result_set += x[1][y]

	return result_set


    def __bind(self):
	self.l.simple_bind_s("uid=%s,ou=systemIDs,o=baplc.com,dc=pathway" % self.sid, self.password)


    def __unbind(self):
	try:
	    self.l.unbind_s()
	except:
	    pass


    def __validate(self,name):
	validname = '^\w+[\w\d\-]*$'
	if type(name).__name__ != 'list':
	    name = [name]

	for n in name:
	    if re.match(validname,n):
		return True

	    raise ValueError, "%s is not a valid name" % n


    def __del__(self):
	try:
	    self.__unbind()
	except:
	    pass


    def getHostgroups(self):
	return self.__search('ou=hostgroups,ou=unix,ou=apps,o=baplc.com,dc=pathway', 'cn=*', ['cn'])


    def getHostgroupHosts(self,hostgroup):
	self.__validate(hostgroup)
	return self.__search('ou=hostgroups,ou=unix,ou=apps,o=baplc.com,dc=pathway', "cn=%s" % hostgroup, ['host'])


    def getHostHostgroups(self,host):
	self.__validate(host)
	return self.__search('ou=hostgroups,ou=unix,ou=apps,o=baplc.com,dc=pathway', "host=%s" % host, ['cn'])

    def addHostsToHostgroup(self,hosts,hostgroup):
	self.__validate(hosts)
	self.__validate(hostgroup)
	dn = "cn=%s,ou=hostgroups,ou=unix,ou=apps,o=baplc.com,dc=pathway" % hostgroup
	attrs = [(ldap.MOD_ADD,'host',h.encode('latin-1')) for h in hosts if h not in self.getHostgroupHosts(hostgroup)]
	if attrs:
	    return self.__modify(dn, attrs)
	return True

	
    def delHostsFromHostgroup(self,hosts,hostgroup):
	self.__validate(hosts)
	self.__validate(hostgroup)
	dn = "cn=%s,ou=hostgroups,ou=unix,ou=apps,o=baplc.com,dc=pathway" % hostgroup
	attrs = [(ldap.MOD_DELETE,'host',h.encode('latin-1')) for h in hosts if h in self.getHostgroupHosts(hostgroup)]
	if attrs:
	    return self.__modify(dn, attrs)
	return True
