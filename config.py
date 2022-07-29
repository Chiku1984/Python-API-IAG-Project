import os

class BaseConfig(object):
    PROJECT = "RAPI"
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    PROPAGATE_EXCEPTIONS    = True
    TRAP_BAD_REQUEST_ERRORS = True


class DefaultConfig(BaseConfig):
    #
    # Generic RAPI Config
    #

    DEBUG = True
    CONFIG = '%s/conf/settings.cfg' % BaseConfig.PROJECT_ROOT
    LOG_CONFIG = '%s/conf/logging.ini' % BaseConfig.PROJECT_ROOT
    SCHEMAS = '%s/RAPI/schemas.json' % BaseConfig.PROJECT_ROOT

    #
    # Puppet config
    #

    CMDB_USER = 'ASP_USER'
    CMDB_PASSWD = 'N3wcastl3'
    CMDB_SID = 'YYPRD_APP3'

    #
    # Hiera config
    #

    HIERA_BLACKLIST = [
	'^common$',
	'^RedHat[0-9]+[\.0-9]*$',
	'^[A-Z]+[A-Z_\-]*$',
	'^physical$',
	'^virtual$'
    ]

    #
    # RIP config
    #

    MONGO_HOST = 'yyrobbo104'
    MONGO_PORT = 27017

    #
    # Oasis Config
    #

    OASIS_VIEW_PKS = {
	'serverSlots'	:	['serverId'],
	'rebootSlots'	:	['rebootSlotId'],
	'patchSlots'	:	['patchSlotId']
    }

    #
    # REDIS Config
    #

    REDIS_HOST = 'bal2154prd001.baplc.com'
    REDIS_PORT = 6379
    REDIS_DB = 0

    #
    # RHEV defaults
    #

    RHEV_USER		= 'admin@internal'
    RHEV_PASSWORD	= 'dopeyman1'

    #
    # Satellite/Foreman/Katello config
    #

    COBBLER_API             = 'http://rhn-satellite/cobbler_api'
    SATELLITE_API           = 'http://rhn-satellite/rpc/api'
    SATELLITE_USER          = 'WEBRAPI'
    SATELLITE_PASSWORD      = 'WEBRAPI123'

    FOREMAN_API     = 'https://foreman-prd.baplc.com'
    FOREMAN_USER    = 'admin'
    FOREMAN_PASSWD  = 'changeme'

    KATELLO_API     = 'https://yyprdap25.baplc.com'
    KATELLO_USER    = 'admin'
    KATELLO_PASSWD  = 'Redhat123'

    KS = { 'rhel_5x64': 'RHEL_5_10:1:BritishAirways',
	   'rhel_6x64': 'RHEL_6_6:1:BritishAirways'}

    OS = {
	'rhel_8_x86_64':{
			'ks_profile': 'RHEL_8_0:1:BritishAirways',
			'vm_os_type': 'rhel_8x64'
		},
	'rhel_7_x86_64':{
			'ks_profile': 'RHEL_7_0:1:BritishAirways',
			'vm_os_type': 'rhel_7x64'
		},
	'rhel_7.0_x86_64':{
			'ks_profile': 'RHEL_7_0:1:BritishAirways',
			'vm_os_type': 'rhel_7x64'
		},
	'rhel_7.1_x86_64':{
			'ks_profile': 'RHEL_7_1:1:BritishAirways',
			'vm_os_type': 'rhel_7x64'
		},
	'rhel_6_x86_64':{
			'ks_profile': 'RHEL_6_6:1:BritishAirways',
			'vm_os_type': 'rhel_6x64'
		},
	'rhel_6.7_x86_64':{
			'ks_profile': 'RHEL_6_7:1:BritishAirways',
			'vm_os_type': 'rhel_6x64'
		},
	'rhel_6.6_x86_64':{
			'ks_profile': 'RHEL_6_6:1:BritishAirways',
			'vm_os_type': 'rhel_6x64'
		},
	'rhel_6.5_x86_64':{
			'ks_profile': 'RHEL_6_5:1:BritishAirways',
			'vm_os_type': 'rhel_6x64'
		},
	'rhel_5.10_x86_64':{
			'ks_profile': 'RHEL_5_10:1:BritishAirways',
			'vm_os_type': 'rhel_5x64'
		}
	}

    DEFAULT_KS = 'RHEL_6_6:1:BritishAirways'
    DEFAULT_OS_ARCH = 'x86_64'
    DEFAULT_OS_TYPE = 'rhel'

    CERTS_DIR = "%s/certs" % BaseConfig.PROJECT_ROOT

    LDAP_URI    = 'ldaps://corpldap.baplc.com:636'
    LDAP_SID    = 'sid711'
    LDAP_PASSWD = 'saw7Daly'
