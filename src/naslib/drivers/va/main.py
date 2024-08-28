##############################################################################
# COPYRIGHT Ericsson AB 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the abstract implementation for InfoScale Access
as the Va class which is based on Sfs class. The corresponding NFS resources
classes are imported to register into the Va class.
 """

import re
from ...drivers.sfs.main import Sfs
from ...base import register_resources
from .resources import FileSystemResource, ShareResource, DiskResource, \
    PoolResource, CacheResource, SnapshotResource


@register_resources(FileSystemResource, ShareResource, DiskResource,
                    PoolResource, CacheResource, SnapshotResource)
class Va(Sfs):
    """ Nas driver class for managing Veritas Access  nfs services
    """
    name = 'VA'
    clish_base_cmd = "LANG=C /opt/SYMCsnas/clish/bin/clish -u %s -c '%s'"
    discovery_path = '/opt/SYMCsnas/clish/bin/clish'
    error_regex = re.compile(r'ACCESS\s\w+\sERROR')
    info_regex = re.compile(r'ACCESS\s\w+\sINFO')
