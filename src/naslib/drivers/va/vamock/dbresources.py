##############################################################################
# COPYRIGHT Ericsson AB 2016
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the implementation of the classes based on
SfsMockDb resource to define the VA resources for the Mock Database.
"""

from ..main import Va
from ..resources import FileSystemResource, ShareResource, PoolResource, \
                        CacheResource
from ...sfs.sfsmock.dbresources import SfsMockDbFilesystem, SfsMockDbShare, \
            SfsMockDbDisk, SfsMockDbPool, SfsMockDbSnapshot, SfsMockDbCache, \
            FILESYSTEM_RESTORE_STILL_RUNNING, ROLLSYNC_STATUS_RUNNING, \
            ROLLSYNC_STATUS_NOT_RUNNING
from ...sfs.sfsmock.dbresources import GetCacheSnapshotsForObjects
from ....nasmock.basedbresource import CommandMockDb
from ....nasexceptions import NasExecCommandException
import re

FS_PROPERTIES_TEMPLATE = """
General Info:
===============
Block Size:      8192 Bytes
Version:         Version 11
isa_01:        %(online)s

Primary Tier
============
Size:            %(size)s
Use%%:             -
Layout:          %(layout)s
Mirrors:         -
Columns:         -
Stripe Unit:     0.00 K
Meta Data:       metaOk
FastResync:      Disabled

1. Mirror 01:
List of pools:   %(pool)s
List of disks:   sdb

FS Type:           Normal

Defrag Status: Not Running
Fullfsck Status: Not Running
Resync   Status: Not Running
Rollsync Status: %(rollsync_status)s
Relayout Status: Not Running
"""

CLISH = Va.clish_base_cmd % ("master", "%s")


class VaMockDbFilesystem(SfsMockDbFilesystem):
    """ Database that mocks the information related to the VA file systems.
    """
    type = 'ACCESS'
    display_line = "%(name)s %(online)s %(size)s %(layout)s - - - - - - - "
    display_regex = FileSystemResource.display_regex
    pool_display_regex = PoolResource.display_regex
    share_display_regex = ShareResource.display_regex
    SfsMockDbFilesystem.regexes["vxtask_list"] = re.compile(r"^vxtask\s+list$")
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage fs list"),
        vxprint=CommandMockDb("vxprint"),
        vxdisk_list=CommandMockDb("vxdisk list sdb"),
        vxdisk_listtag=CommandMockDb("vxdisk listtag"),
        vxdg=CommandMockDb("vxdg -q list 1476628227.9.isa_01"),
        vxtask_list=CommandMockDb("vxtask list")
    )

    already_exists_msg = type + " fs ERROR V-288-1140 File system " \
                         "already exists."
    already_offline_msg = type + " fs ERROR V-288-672 Filesystem %s " \
                          "is already offline."
    already_online_msg = type + " fs ERROR V-288-844 Filesystem is " \
                         "already online."

    def properties(self, name):
        if not self.exists(name=name):
            raise NasExecCommandException('%s fs ERROR V-288-646 '
                    'File system %s does not exist.' % (self.type, name))
        kwargs = self.get_entry_kwargs(name=name)
        # TODO: It might be better way to get pool for FS in Mock
        kwargs['pool'] = self.vxdisk_listtag().split()[-1]
        if name == FILESYSTEM_RESTORE_STILL_RUNNING:
            kwargs['rollsync_status'] = ROLLSYNC_STATUS_RUNNING % name
        else:
            kwargs['rollsync_status'] = ROLLSYNC_STATUS_NOT_RUNNING
        return FS_PROPERTIES_TEMPLATE % kwargs

    def vxtask_list(self):
        """ Simulates the "vxtask list" command call and return the contents
        from the SFS Mock Database json.
        """
        return self.read('vxtask_list')


class VaMockDbShare(SfsMockDbShare):
    """ Database that mocks the information related to the VA shares.
    """
    type = 'ACCESS'
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "nfs share show")
    )


class VaMockDbDisk(SfsMockDbDisk):
    """ Database that mocks the information related to the VA disks.
    """
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage disk list")
    )


class VaMockDbPool(SfsMockDbPool):
    """ Database that mocks the information related to the VA pools.
    """
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage pool list")
    )


class VaMockDbSnapshot(SfsMockDbSnapshot):
    """ Database that mocks the information related to the VA pools.
    """

    type = 'ACCESS'
    cache_display_regex = CacheResource.display_regex
    filesystem_match_display_regex = VaMockDbFilesystem.match_display_regex
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage rollback list"),
        cache=GetCacheSnapshotsForObjects(start_data=2,
                    cmd=CLISH % "storage rollback cache list",
                    second_cmd=CLISH % "storage rollback cache list {0}"),
    )
    already_offline_msg = type + " fs ERROR V-288-672 Filesystem %s " \
                          "is already offline."
    already_online_msg = type + " fs ERROR V-288-844 Filesystem is " \
                         "already online."

    def _get_filesystem_by_rollback_name(self, name):
        """ Gets the file system name given a rollback name.
        """
        fs = ""
        for line in self.list().splitlines():
            match = SfsMockDbSnapshot.match_display_regex(line)
            if match and match.groupdict()['name'] == name:
                fs = match.groupdict()['filesystem']
        for line in self.resources.fs.list().splitlines():

            match = self.filesystem_match_display_regex(line)
            if match and match.groupdict()['name'] == fs:
                fs_kwargs = match.groupdict()
                # TODO: It might be better way to get pool for FS in Mock
                pool = self.resources.fs.vxdisk_listtag().split()[-1]
                fs_kwargs['pool'] = pool
                return fs_kwargs


class VaMockDbCache(SfsMockDbCache):
    """ Database that mocks the information related to the VA caches.
    """
    type = 'ACCESS'
    display_line = "%(name)s %(size)s %(used)s (1.00) %(available)s " \
                   "(99.00) 0"
    display_regex = CacheResource.display_regex
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage rollback cache list"),
    )

    def list_snapshots(self, name):
        """ Simulates the list of snapshots given a cache name, providing
        likely the same output as VA does executing the command
        "storage rollback cache list <CACHE_NAME>". Please refer to the
        SfsMockDbSnapshot.after_insert method for better understanding.
        """
        caches = self.resources.snapshot.read('cache')
        snapshots = caches.get(name, [])
        result = "\nRollback list\n=============\n{0}".format(
                                                        '\n'.join(snapshots))
        return result
