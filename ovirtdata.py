#!/usr/bin/python

import threading
import datetime
import time
import argparse
import functools
import json
import sys

class OvirtDataFormatter(object):
    '''Class: OvirtDataFormatter

    '''
    def __init__(self,manager):
	self.manager = manager


    def __rgetattr(self, obj, attr):
	'''__rgetattr

	Private method for recursively obtaining the value of nested attributes
	E.g. 'obj.status.state'
	'''
	def _getattr(obj, name):
	    return getattr(obj, name, '')
	return str(functools.reduce(_getattr, [obj]+attr.split('.')))

	
    def __format_data(self,data,keymap,static_attr={}):
	'''__format_data

	Generic method for formatting object attributes into a list of
	dictionaries.

	A keymap must be provided to map object attributes into dictionary keys.

	An optional dictionary of static key-value pairs can be supplied. This
	is added to each dictionary in the list if specified.
	'''
	ret = dict([(k,self.__rgetattr(data,v)) for k,v in keymap.iteritems()])
	if static_attr:
	    ret.update(static_attr)
	return ret


    def __format_data_center(self,data,keymap):
	'''__format_data_centers

	Wrapper method for __format_data. Defines the static attributes
	required when formatting an Ovirt data center object.
	'''
	static_attr = { 'managerName'          : self.manager,
                        'virtDatacentreTypeNm' : 'RHEV' }
	return self.__format_data(data,keymap,static_attr)


    def __format_host(self,data,keymap):
	'''__format_hosts

	Wrapper method for __format_data. Defines the static attributes
	required when formatting an Ovirt host object.
	'''
	static_attr = { 'managerName'  : self.manager,
			'hostTypeName' : 'RHEV' }
	return self.__format_data(data,keymap,static_attr)


    def __format_vm(self,data,keymap):
	'''__format_vms

	Wrapper method for __format_data. Defines the static attributes
	required when formatting an Ovirt vm object.
	'''
	static_attr = { 'machineTypeName' : 'RHEV',
			'managerName'     : self.manager }
	return self.__format_data(data,keymap,static_attr)


    def __format_cluster(self,data,keymap):
	'''__format_vms

	Wrapper method for __format_data. Defines the static attributes
	required when formatting an Ovirt cluster object.
	'''
	static_attr = { 'clusterTypeName' : 'RHEV',
			'managerName'     : self.manager }
	return self.__format_data(data,keymap,static_attr)


    def __format_storage_pool(self,sd,keymap):
	'''__format_vms

	Wrapper method for __format_data. Defines the static attributes
	required when formatting an Ovirt storage domain object.

	The storage domain object is modified to include 'size' and 'free'
	attributes derived from basic arithmetic of existing objects.
	'''
	static_attr = { 'storagePoolTypeName' : 'RHEV',
			'managerName'         : self.manager }

	try:
	    sd.size = str(int(round((sd.available + sd.used) / (1024*1024*1024))))
	except:
	    sd.size = ''	# set to '' if object contains no utilisation 
	try:
	    sd.free = str(int(round(sd.available / (1024*1024*1024))))
	except:
	    sd.free = ''
	return self.__format_data(sd,keymap,static_attr)


class Ovirt3DataFormatter(OvirtDataFormatter):
    '''Class: Ovirt3DataFormatter

    '''
    def __init__(self,manager):
	self.manager = manager


    def __del__(self):
	pass


    def format_data_center(self,dc):
	'''format_data_centers

	'''
	keymap = { 'virtualDatacentreId'    : 'id',
                   'virtualDatacentreName'  : 'name',
		   'virtualDatacentreState' : 'status.state' }

	return self._OvirtDataFormatter__format_data_center(dc,keymap)


    def format_host(self,host):
	'''format_hosts

	'''
        keymap = { 'virtualHostId'    : 'id',
                   'virtualHostName'  : 'name',
                   'virtualHostState' : 'status.state',
                   'clusterId'        : 'cluster.id' }

        return self._OvirtDataFormatter__format_host(host,keymap)


    def format_vm(self,vm):
	'''format_vms

        '''
        keymap = { 'virtualMachineId'    : 'id',
                   'virtualMachineName'  : 'name',
                   'virtualMachineState' : 'status.state',
		   'virtualHostId'	 : 'host.id',
                   'clusterId'           : 'cluster.id' }

        return self._OvirtDataFormatter__format_vm(vm,keymap)


    def format_cluster(self,cluster):
	'''format_clusters

        '''
        keymap = { 'clusterId'           : 'id',
                   'virtualDatacentreId' : 'data_center.id',
                   'clusterName'         : 'name' }

        return self._OvirtDataFormatter__format_cluster(cluster,keymap)


    def format_storage_pool(self,storagepool):
	'''format_storage_pools

	'''
        keymap = { 'storagePoolId'        : 'id',
                   'virtualDatacentreId'  : 'data_center.id',
                   'storagePoolName'      : 'name',
                   'storagePoolSize'      : 'size',
		   'storagePoolState'	  : 'status.state',
                   'storagePoolFreeSpace' : 'free' }

        return self._OvirtDataFormatter__format_storage_pool(storagepool,keymap)


class Ovirt4DataFormatter(OvirtDataFormatter):
    '''Class: Ovirt4DataFormatter

    '''
    def __init__(self,manager):
	self.manager = manager


    def format_data_center(self,dc):
	'''format_data_centers

	'''
	keymap = { 'virtualDatacentreId'    : 'id',
		   'virtualDatacentreName'  : 'name',
		   'virtualDatacentreState' : 'status' }

	return self._OvirtDataFormatter__format_data_center(dc,keymap)


    def format_host(self,host):
	'''format_hosts

	'''
	keymap = { 'virtualHostId'    : 'id',
		   'virtualHostName'  : 'name',
                   'virtualHostState' : 'status',
		   'clusterId'	      : 'cluster.id' }

	return self._OvirtDataFormatter__format_host(host,keymap)


    def format_vm(self,vm):
	'''format_vms

        '''
	keymap = { 'virtualMachineId'    : 'id',
		   'virtualMachineName'  : 'name',
		   'virtualMachineState' : 'status',
		   'clusterId'		 : 'cluster.id' }

	return self._OvirtDataFormatter__format_vm(vm,keymap)


    def format_cluster(self,cluster):
	'''format_clusters

        '''
	keymap = { 'clusterId'           : 'id',
		   'virtualDatacentreId' : 'data_center.id',
		   'clusterName'	 : 'name' }

	return self._OvirtDataFormatter__format_cluster(cluster,keymap)


    def format_storage_pool(self,storagepool):
	'''format_storage_pools

	'''
	keymap = { 'storagePoolId'        : 'id',
		   'virtualDatacentreId'  : 'data_center.id',
		   'storagePoolName'	  : 'name',
		   'storagePoolSize'      : 'size',
		   'storagePoolState'     : 'status',
		   'storagePoolFreeSpace' : 'free' }

	return self._OvirtDataFormatter__format_storage_pool(storagepool,keymap)
