#!/usr/bin/python

import threading
import datetime
import time
import argparse
import functools
import json
import sys
from operator import itemgetter, attrgetter
from time import sleep
import rpyc

import redis
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class API(object):
    '''Class: API

    '''
    def __init__(self,url,username,password,ca_file=None,insecure=True,rpychost='bal2154prd001'):
        self.url = url
        self.username = username
        self.password = password
        self.ca_file = ca_file
        self.insecure = insecure
        self.conn = rpyc.classic.connect(rpychost)
        self.types = self.conn.modules.ovirtsdk4.types

        self.initialise()

    def initialise(self):
        self.api = self.conn.modules.ovirtsdk4.Connection(
                        url = self.url,
                        username = self.username,
                        password = self.password,
                        ca_file = self.ca_file,
                        insecure = self.insecure
                        )

        self.Cluster = Cluster(self)
        self.Network = Network(self)
        self.VM = VM(self)

        return self.test()

    def disconnect(self):
        try:
            self.api.close()
        except:
            pass

    def test(self):
        try:
            self.api.test(throw_exception=True)
            return True
        except:
            return False


    def __del__(self):
        self.disconnect()



class Cluster():
    def __init__(self,base):
        self.api = base.api
        self.base = base


    def list(self,name=None):
        clusters_service = self.api.system_service().clusters_service()

        if name:
            try:
                cluster = clusters_service.list(search='name=%s' % str(name))[0]
                return cluster
            except IndexError:
                return None

        return clusters_service.list(max=10000)


    def listNetworks(self,name=None,cluster=None):
        '''Cluster.listNetworks

        '''
        if not cluster and not name:
            raise ValueError, 'You must supply either a cluster object or a cluster name'

        if not cluster:
            cluster = self.list(name)

        cluster_service = self.api.system_service().clusters_service().cluster_service(cluster.id)
        return cluster_service.networks_service().list()


    def getStorageDomain(self,cluster=None,storageDomain=None):
        '''Cluster.getStorageDomain

        '''
        if not cluster:
            raise ValueError, 'A cluster name must be specified'

        clu = self.api.system_service().clusters_service().list(search='name=%s' % str(cluster))[0]

        datacenter_id = clu.data_center.id

        if storageDomain:
            try:
                dcsd = self.api.system_service().data_centers_service().data_center_service(datacenter_id).storage_domains_service().list(query='name=%s' % storageDomain)[0]
            except:
                raise ValueError, 'No storage domain %s accessible by cluster %s' % (storageDomain,cluster)

            return dcsd

        dcsds = self.api.system_service().data_centers_service().data_center_service(datacenter_id).storage_domains_service().list()

        if not dcsds:
            raise Exception, 'No storage domain found for cluster %s' % cluster

        allocatable_domains =  [x for x in dcsds if x.type == self.base.conn.modules.ovirtsdk4.types.StorageDomainType.DATA and x.name != 'hosted_storage']

        return sorted(allocatable_domains,key=lambda x: x.available, reverse=True)[0]



class Network():
    def __init__(self,base):
        self.api = base.api
        self.base = base


    def list(self,id):
        return self.api.system_service().vnic_profiles_service().profile_service(id).get()


    def getVNICProfile(self,name,vm=None,vmname=None,throw_exception_if_missing=True):
        '''Network.getVNICProfile

        '''
	if not vm and not vmname:
	    raise ValueError, 'Either a VM name or a VM object must be supplied'

	# we need to get the cluster object so that we can ...
	if not vm:
	    vm_cluster = self.base.VM.getCluster(name=name)
	else:
	    vm_cluster = self.base.VM.getCluster(vm=vm)

	# .. get the networks that are attached to its cluster
	clu_networks = self.base.Cluster.listNetworks(cluster=vm_cluster)

	# create a list of cluster network ids
	clu_network_ids = [x.id for x in clu_networks]

        profiles_service = self.api.system_service().vnic_profiles_service()
        for profile in profiles_service.list():
            if profile.name == name and profile.network.id in clu_network_ids:
                return profile

        if throw_exception_if_missing:
            raise ValueError, 'Cannot find VM network with name %s' % name

        return None



class VM():
    def __init__(self,base):
        self.api = base.api
        self.base = base


    def list(self,name=None):
        vms_service = self.api.system_service().vms_service()

        if name:
            try:
                vm = vms_service.list(search='name=%s' % str(name))[0]
                return vm
            except IndexError:
                return None

        return vms_service.list(max=10000)


    def listNICs(self,name=None):
        vm = self.list(name)

        nics_service = self.api.system_service().vms_service().vm_service(vm.id).nics_service()

        return nics_service.list()


    def getCluster(self,name=None,vm=None):
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
	    vm = self.base.VM.list(name)

	return self.api.system_service().clusters_service().cluster_service(id=vm.cluster.id).get()


    def getMACAddress(self,name,nic='eth0'):
        for vmnic in self.listNICs(name):
            if vmnic.name == nic:
                return vmnic.mac.address

        raise Exception, 'VM %s does not have a nic named %s' % (name,nic)


    def add(self,vmName=None,memory=None,cluster=None,storagedomain=None,template='Blank',display='spice',desc=None,type='server',cpu={'cores':1,'sockets':2},ha={'enabled':True,'priority':10},os={}):
        '''VM.add

        '''
        MB = 1024*1024
        GB = 1024*MB

        # if we're not building from a template we need to ensure that the OS type is set
        if template == 'Blank':
            # raise exception if the OS type is not specified
            if not 'type' in os:
                raise ValueError, 'No OS type specified'

        # general parameters that are shared between template and non-template builds
        VMparams = self.base.conn.modules.ovirtsdk4.types.Vm(
                        name=vmName,
                        memory=int(memory*GB),
                        type=self.base.types.VmType(type),
                        cluster=self.base.types.Cluster(name=cluster),
                        template=self.base.types.Template(name=template),
                        cpu=self.base.types.Cpu(topology=self.base.types.CpuTopology(
                                cores=cpu['cores'],
                                sockets=cpu['sockets'])),
                        display=self.base.types.Display(type=self.base.types.DisplayType(display)),
                        description=desc,
                        usb=self.base.types.Usb(enabled=False),
                        high_availability=self.base.types.HighAvailability(
                                enabled=ha['enabled'],
                                priority=ha['priority'])
                )

        # if we're building from a template ..
        if template != 'Blank':

            #
            # sort out the OS disk parameters for the clone operations
            #

            ### TBC
            pass

        # if we're NOT building from a template ..
        else:
            # add the OS definition .. we don't inherit this from the template
            VMparams.os = self.base.types.OperatingSystem(
                                type=os['type'],
                                boot=self.base.types.Boot(devices=[
                                        self.base.types.BootDevice('hd'),
                                        self.base.types.BootDevice('network')]))


        vms_service = self.api.system_service().vms_service()

        return vms_service.add(VMparams)


    def addNIC(self,vm,name=None,mac=None,network=None,interface='virtio'):
        '''VM.addNIC

        '''
        if network:
            profile = self.base.Network.getVNICProfile(vm=vm,name=network)

            vnic_profile = self.base.types.VnicProfile(id=profile.id)

        else:
            vnic_profile = None

        nics_service = self.api.system_service().vms_service().vm_service(vm.id).nics_service()

        nics_service.add(
            self.base.types.Nic(
                name=name,
                mac=mac,
                vnic_profile=vnic_profile,
                interface=self.base.types.NicInterface(interface)
            ),
        )


    def addDisk(self,vm,size,domain,type='system',bootable=None,interface='virtio',format='raw',sparse=False):
        MB=1024*1024
        GB=1024*MB
        # ignore whatever value for bootable is passed
        # only a system disk can be bootable
        if type == 'system':
            bootable=True
        else:
            bootable=False

        # size should be in GB; however, assume bytes if the size
        # is too big to possibly be GB
        if int(size) < 99999:
            size=int(size) * 2**30

        vms_service = self.api.system_service().vms_service()
        disk_attachment_service = vms_service.vm_service(vm.id).disk_attachments_service()

        disk_attachment = disk_attachment_service.add(
                                self.base.types.DiskAttachment(
                                    disk=self.base.types.Disk(
                                        storage_domains=[self.base.types.StorageDomain(id=domain.id)],
                                        provisioned_size=size,
                                        format=self.base.types.DiskFormat(format),
                                        sparse=sparse
                                    ),
                                    interface=self.base.types.DiskInterface(interface),
                                    bootable=bootable
                                )
                        )


    def create(self,name=None,memory=None,cluster=None,storagedomain=None,template='Blank',display='spice',desc=None,type='server',cpu={'cores':1,'sockets':2},ha={'enabled':True,'priority':10},os={},nics=None,disks=None):
        '''VM.create

        '''

        # raise ValueErrors if required parameters are not specified

        if not name:
            raise ValueError, "No VM name specified!"

        if not memory:
            raise ValueError, "No memory specified!"

        if not cluster:
            raise ValueError, "No cluster specified!"

        if not nics:
            raise ValueError, "No NICs defined!"

        if not disks:
            raise ValueError, "No disks defined!"

        if self.list(name):
            raise Exception, "VM %s already exists!" % name

        # get the storage domain object for the specified cluster
        # we do this operation once, in advance, as it is required multiple times in the following processing
        sd = self.base.Cluster.getStorageDomain(cluster=cluster,storageDomain=storagedomain)

        # create the VM
        vm = self.add(vmName=name,cpu=cpu,memory=memory,cluster=cluster,os={'type':'rhel_7x64'})

        # post-creation tasks ...
        # these differ depending on whether the VM was cloned from a template or created from scratch
        try:
            # if we're building from a template image
            if template != 'Blank':

                # ensure that the VM nics are configured correctly ...
                # we don't create them, we update them with the requested configuration
                pass

                # wait until the template cloning operation has completed ...
                pass

                # ... before we add the data disk(s)
                pass

                # the template cloning action sometimes loses the root password
                # setting - let's re-add it just in case
                pass

            # if we're building from scratch
            else:

                # add NICs to the VM
                for nic in sorted(nics, key=itemgetter('name')):
                    self.addNIC(vm=vm,**nic)
                    print 'Added NIC %s to VM %s' % (nic['name'],vm.name)

            # add each disk to the VM
            for disk in disks:
                self.addDisk(vm=vm,domain=sd,**disk)

        # remove the VM on error
        except Exception as e:
            print str(e)
            self.delete(name)
            raise Exception(str(e))

        # only return once the VM is built and in a position to boot
        self.waitForDiskState(vm=vm,state='ok')

        return self.list(name)


    def waitForState(self,vm=None,name=None,states=None,failure_states=None,timeout=120,interval=5):
        if not vm and not vmName:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        vm_service = self.api.system_service().vms_service().vm_service(vm.id)

        counter = 0
        while counter < timeout:
            sleep(interval)
            counter += interval
            state = str(vm_service.get().status)
            if state in states:
                return True

            if failure_states and state in failure_states:
                raise Exception, "VM failed with state : %s" % state

        raise Exception, "Timed out waiting for operation!"


    def waitForDiskState(self,vm=None,name=None,state=None,timeout=120):
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        disk_attachments_service = self.api.system_service().vms_service().vm_service(vm.id).disk_attachments_service()
        disk_attachments = disk_attachments_service.list()

        counter = 0
        while counter < timeout:
            sleep(1)
            counter += 1
            if not [x for x in [self.api.follow_link(d.disk) for d in disk_attachments] if str(x.status) != state]:
                return True

        return False


    def start(self,name=None,vm=None,wait=False):
        '''VM.start

        '''
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        self.api.system_service().vms_service().vm_service(vm.id).start()

        if wait:
            return self.waitForState(vm=vm,states=['up'])
        return True


    def shutdown(self,name=None,vm=None,wait=False):
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        self.api.system_service().vms_service().vm_service(vm.id).shutdown()

        if wait:
            return self.waitForState(vm=vm,states=['down'])
        return True


    def stop(self,name=None,vm=None,wait=False):
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        self.api.system_service().vms_service().vm_service(vm.id).stop()

        if wait:
            return self.waitForState(vm=vm,states=['down'])
        return True


    def delete(self,name=None,vm=None):
        if not vm and not name:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(name)

        vms_service = self.api.system_service().vms_service()

        if vm.status != self.base.types.VmStatus.DOWN:
            self.stop(vm=vm,wait=True)

        vm_service = vms_service.vm_service(vm.id)
        vm_service.remove()


    def updateNICs(self,nics,vm=None,vmName=None):
        if not vm and not vmName:
            raise ValueError, "A VM name or VM object must be supplied"

        if not vm:
            vm = self.list(vmName)

        nics_service = self.api.system_service().vms_service().vm_service(vm.id).nics_service()

        vmnics = nics_service.list()

        if not vmnics:
            raise ValueError, 'VM %s does not have any nics!' % vm.name

        indexed_vmnics = dict((nic.name,nic) for nic in vmnics)

        # raise an exception if we're attempting to update a NIC that is not on the VM
        for nic in nics:
            if nic['name'] not in indexed_vmnics:
                raise ValueError, 'VM %s does not contain an %s nic' % (vm.name,nic['name'])

        for nic in nics:
            vmnic = indexed_vmnics[nic['name']]
            nic_service = nics_service.nic_service(vmnic.id)

            if 'network' in nic:
                profile = self.base.Network.getVNICProfile(vm=vm,name=nic['network'])
                vnic_profile = self.base.types.VnicProfile(id=profile.id)
            else:
                vnic_profile = None

            if 'mac' in nic:
                mac = self.base.types.Mac(address=nic['mac'])
            else:
                mac = None

            nic_service.update(
                self.base.types.Nic(
                    mac=mac,
                    vnic_profile=vnic_profile
                )
            )

        return True
