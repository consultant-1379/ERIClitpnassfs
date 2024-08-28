##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the implementation of the classes based on
SfsMockDbResourceBase to define the SFS resources for the Mock Database.
"""

import re
from decimal import Decimal, ROUND_UP

from ....resourceprops import Size
from ....nasexceptions import NasExecCommandException
from ..main import Sfs
from ..resources import FileSystemResource, ShareResource, DiskResource, \
                        PoolResource, CacheResource, SnapshotResource
from ..utils import VxCommandsException
from ....nasmock.basedbresource import CommandMockDb, StopInsertException
from ....nasmock.dbresources import BaseMockDbFilesystem, BaseMockDbShare, \
    BaseMockDbDisk, BaseMockDbPool, BaseMockDbCache, BaseMockDbSnapshot

ANY_GENERIC_ERROR = 'ANY_GENERIC_ERROR'
FORCE_ERROR_ONLINE = 'FORCE_ERROR_ONLINE'
FORCE_ERROR_OFFLINE = 'FORCE_ERROR_OFFLINE'
ANY_ERROR_FOR_FS_RESIZE = 'ANY_ERROR_FOR_FS_RESIZE'
FORCE_FS_BECOME_ONLINE_AFTER_RESTORE = 'FORCE_FS_BECOME_ONLINE_AFTER_RESTORE'
FILESYSTEM_FORCE_RESTORE_FAIL = 'FSRESTFAIL'
FILESYSTEM_RESTORE_STILL_RUNNING = 'FSRESTRUN'

# !!! needs to be updated always when updating the resources.mock.json data.
FAULTED_SHARES = [
    '/vx/ST72-fs2     10.44.86.72: CLUSTER_NAME',
    '/vx/Int38-int38  10.44.86.22: CLUSTER_NAME'
]  # !!! needs to be updated always when updating the resources.mock.json data.

FS_PROPERTIES_TEMPLATE = """
General Info:
===============
Block Size:      1024 Bytes
Version:          Version 8
SFS_01:        %(online)s

Primary Tier
============
Size:            %(size)s
Use%%:            -
Layout:          %(layout)s
Mirrors:         -
Columns:         -
Stripe Unit:     0.00 K
FastResync:      Enabled

1. Mirror 01:
List of pools:   %(pool)s
List of disks:   sdb

Defrag Status: Not Running
Fullfsck Status: Not Running
Resync   Status: Not Running
Rollsync Status: %(rollsync_status)s
Relayout Status: Not Running
"""

ROLLSYNC_STATUS_NOT_RUNNING = "Not Running"
ROLLSYNC_STATUS_RUNNING = "\n    Rollback %s, Tier 1: 83.59%%  Start_time: " \
            "Jul/15/2015/11:33:19   Work_time: 0:0:46     Remaining_time: 0:09"
CLISH = Sfs.clish_base_cmd % ("master", "%s")


def get_faulted_shares():
    faulted_shares = []
    form = ShareResource.faulted_match_format
    for faulted in FAULTED_SHARES:
        match = ShareResource.faulted_shares_regex.match(faulted)
        faulted_shares.append(form % match.groupdict())
    return faulted_shares


class GetCacheSnapshotsForObjects(CommandMockDb):
    """ This class extract from the SFS the snapshot list for the given
    cache using predefined commands. This class is used to update the
    MockDB "resources.mock.json".
    """
    def __init__(self, start_data=1, cmd=CLISH % "storage rollback cache list",
                 second_cmd=CLISH % "storage rollback cache list {0}"):
        """ Uses the Sfs.clish_base_cmd clish to run the
        command as "master" user on the SFS to generate MockDB.
        """
        super(GetCacheSnapshotsForObjects, self).__init__(cmd)
        self.second_cmd = second_cmd
        self.start_data = start_data

    def extract_data(self, ssh):
        """ This method runs both command, process them to generate the
            cache dictionary that contains the list of the snapshots.
            {"Int51-cache": ["Int51-int51-s", "Int51-storadm_51-s"]}
        >>> from naslib.nasmock.ssh import SshClientMock
        >>> from naslib.drivers.sfs.sfsmock.db import SfsMockDb
        >>> a = GetCacheSnapshotsForObjects()
        >>> ssh = SshClientMock("host", "user", "password",
        ...                     mock_db=SfsMockDb())
        >>> data = a.extract_data(ssh)
        >>> type(data)
        <type 'dict'>
        """
        output = ssh.run(self.cmd)[1].strip()
        lines = output.splitlines()
        caches = [line.split()[0].strip() for line in lines[self.start_data:]
                  if line.strip()]
        snapshots_cache = {}
        for cache in caches:
            process = None
            snapshots_cache[cache] = []
            output = ssh.run(self.second_cmd.format(cache))[1].strip()
            lines = output.splitlines()
            for line in lines:
                if process:
                    snapshots_cache[cache].append(line.strip())
                if (line.startswith("rollbacks located on cache") or
                        line.startswith("===========")):
                    process = True
        return snapshots_cache


class SfsMockDbFilesystem(BaseMockDbFilesystem):
    """ Database that mocks the information related to the SFS file systems.
    """
    name = "fs"
    type = 'SFS'
    identifier = "name"
    display_line = "%(name)s %(online)s %(size)s %(layout)s - - - - - - " \
                   "%(pool)s"
    display_regex = FileSystemResource.display_regex
    pool_display_regex = PoolResource.display_regex
    share_display_regex = ShareResource.display_regex
    regexes = dict(
        list=re.compile(r"^storage\s+fs\s+list$"),
        insert=re.compile(r"^storage\s+fs\s+create\s+(?P<layout>[-\w]+)\s+"
                          r"(?P<name>[-\w]+)\s+(?P<size>\d+[kmgtKGMT]{1})\s+"
                          r"(?P<pool>[-\w]+)$"),
        delete=re.compile(r"^storage\s+fs\s+destroy\s+(?P<name>[-\w]+)$"),
        offline=re.compile(r"^storage\s+fs\s+offline\s+(?P<name>[\w-]+)$"),
        online=re.compile(r"^storage\s+fs\s+online\s+(?P<name>[\w-]+)$"),
        growto=re.compile(r"^storage\s+fs\s+growto\s+primary\s+"
                          r"(?P<name>[\w-]+)\s+(?P<size>\d+[kmgtKGMT]{1})"
                          r"\s+(?P<pool>[-\w]+)?$"),
        properties=re.compile(r"^storage\s+fs\s+list\s+(?P<name>[\w-]+)$"),
        vxprint=re.compile(r"^vxprint -hrAF sd:'%type %name %assoc %kstate "
            "%len %column_pl_offset %state %tutil0 %putil0 %device'$"),
        vxprint_name=re.compile(r"^vxprint -hrAF sd:'%type %name %assoc "
            r"%kstate %len %column_pl_offset %state %tutil0 %putil0 "
            r"%device'\s+(?P<name>[-\w]+)$"),
        vxdisk_list=re.compile(r"^vxdisk\s+list\s+[-\.\w]+$"),
        vxdisk_listtag=re.compile(r"^vxdisk\s+listtag$"),
        vxdg=re.compile(r"^vxdg\s+-q\s+list\s+[-\.\w]+$"),
        vxprint_simple=re.compile(r"vxprint"),
        vxedit=re.compile(r"vxedit -rf rm mycache_tier1")
    )
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage fs list"),
        vxprint=CommandMockDb("vxprint"),
        vxdisk_list=CommandMockDb("vxdisk list emc_clariion0_110"),
        vxdisk_listtag=CommandMockDb("vxdisk listtag"),
        vxdg=CommandMockDb("vxdg -q list 1359985462.17.ammsfs_01")
    )
    already_exists_msg = type + " fs ERROR V-288-170 File system %(name)s " \
                         "already exists"
    pool_does_not_exist_msg = type + " fs ERROR V-288-678 Pool(s) or " \
                                     "disk(s) %s does not exist."
    insufficient_space_msg = type + " fs ERROR V-288-921 Unable to create fs "\
        "%s due to either insufficient space/unavailable disk. Please run " \
        "scanbus."
    already_offline_msg = type + " fs ERROR V-288-843 Filesystem is " \
                                 "already offline."
    already_online_msg = type + " fs INFO V-288-1878 Filesystem is " \
            "already online on master node, trying to mount on all the nodes."
    shared_cannot_offlined = type + " fs ERROR V-288-672 NFS shared " \
                                    "file system cannot be offlined."

    def vxedit(self):
        """ Simulates the vxedit command to remove the underlying
        cache volumes.
        """
        return self.read('vxedit')

    def vxprint_simple(self):
        """ Simulates the vxprint command call and return the contents from
        the SFS Mock Database json.
        """
        return self.read('vxprint_simple')

    def vxprint(self):
        """ Simulates the vxprint command call and return the contents from
        the SFS Mock Database json.
        """
        return self.read('vxprint')

    def vxprint_name(self, name):
        """ Simulates the vxprint command call by name and return the contents
        from the SFS Mock Database json.
        """
        output = self.read('vxprint')
        blocks = output.split('\n\n')
        data = [b for b in blocks if b.strip() and
                b.strip().splitlines()[0].split()[1] == name][0]
        return "%s\n\n%s\n\n%s" % (blocks[0], blocks[1], data)

    def vxdisk_list(self):
        """ Simulates the "vxdisk list" command call and return the contents
        from the SFS Mock Database json.
        """
        return self.read('vxdisk_list')

    def vxdisk_listtag(self):
        """ Simulates the "vxdisk listtag" command call and return the contents
        from the SFS Mock Database json.
        """
        return self.read('vxdisk_listtag')

    def vxdg(self):
        """ Simulates the "vxdisk listtag" command call and return the contents
        from the SFS Mock Database json.
        """
        return self.read('vxdg')

    def before_insert(self, **kwargs):
        """ Overrides the base method to do some actions before insert data
        into the SFS Mock database json. Basically simulates the validation
        messages done in real SFS server, throwing NasExecCommandException
        to be caught in the main methods of NAS resources (such as list, get,
        exists, create, delete, resize, etc) after calling the execute()
        method.
        """
        # test pool
        pool = kwargs['pool']
        invalid_pool = True
        for line in self.resources.pool.list().splitlines():
            match = self.pool_display_regex.match(line)
            if not match:
                continue
            if match.groupdict()['name'] == pool:
                invalid_pool = False
                break
        if invalid_pool:
            raise NasExecCommandException(self.pool_does_not_exist_msg % pool)

        # test huge size
        size = kwargs['size']
        fs = kwargs['name']
        if Size(size) >= Size("999999T"):
            raise NasExecCommandException(self.insufficient_space_msg % fs)

        # any generic error
        if kwargs['name'] == ANY_GENERIC_ERROR:
            raise NasExecCommandException("Any generic error message")

    def after_insert(self, **kwargs):
        """ Overrides the base method to do some actions after insert data
        into the SFS Mock database json. In this case inserts new data in the
        'vxprint' mock database, so it will be available for listing after
        that.
        """
        # includes an entry in vxprint related to this filesytem name and
        # also makes the proper calculation of size blocks in terms of
        # disk alignment in 8k.
        size = Size(kwargs['size'])
        num_bytes = size.num_bytes
        alignment = (1024 * 8)
        rest = size.num_bytes % alignment
        if rest != 0:
            num_bytes += alignment - rest
        blocks_size = num_bytes / 512
        vxprint = """

vt %(fs)s -     ENABLED  -        -        ACTIVE   -       -
v  %(fs)s_tier1 %(fs)s ENABLED %(size)s - ACTIVE - -
pl %(fs)s_tier1-01 %(fs)s_tier1 ENABLED %(size)s - ACTIVE - -
sd emc_clariion0_110-102 %(fs)s_tier1-01 ENABLED %(size)s 0 - - - sda
        """ % dict(fs=kwargs['name'], size=blocks_size)
        self.write('vxprint', vxprint)

    def prepare_insert_kwargs(self, **kwargs):
        """ Just includes the online value.
        """
        kwargs['online'] = 'online'
        return kwargs

    def offline(self, name):
        """ Modifies the fs database to changing the 'online' column entry to
        'offline' value. It also checks whether the file system has or not
        any shares underneath, raising the proper error message.
        """
        for line in self.resources.share.list().splitlines():
            match = self.share_display_regex.match(line)
            if not match:
                continue
            data = match.groupdict()
            if data['name'].endswith(name):
                raise NasExecCommandException(self.shared_cannot_offlined)
        exc = NasExecCommandException(self.already_offline_msg)
        self.update(exception_if_the_same=exc, name=name, online='offline')

    def online(self, name):
        """ Modifies the fs database to changing the 'online' column entry to
        'offline' value. If passes the FORCE_ERROR_ONLINE as name argument,
        raise a generic error, to mock any error situation.
        """
        if name == FORCE_ERROR_ONLINE:
            raise NasExecCommandException("Any generic error message while "
                                          "trying to bring fs online")
        exc = NasExecCommandException(self.already_online_msg)
        self.update(exception_if_the_same=exc, name=name, online='online')

    def growto(self, name, size, pool=None):  # pylint: disable=I0011,W0613
        """ Modifies the fs and vxprint databases changing the size.
        """
        if name == ANY_ERROR_FOR_FS_RESIZE:
            raise NasExecCommandException("any error")

        if size == '99950G':
            return "Filesystem %s usage is over 95%%. If the grow did not " \
                   "succeed, remove some files and try again." % name

        if size >= '9999999T':
            raise NasExecCommandException("%s fs ERROR V-288-2128 Unable to "
                      "allocate space " \
                      "to grow fs %s due to either insufficient " \
                      "space/unavailable disk" % (self.type, name))

        for line in self.list().splitlines():
            match = self.match_display_regex(line)
            if match and match.groupdict()['name'] == name:
                if match.groupdict()['online'] == 'offline':
                    raise NasExecCommandException("%s fs ERROR V-288-685 %s" \
                                " must be online to perform grow " \
                                "operation." % (self.type, name))

        self.update(name=name, size=size)
        lines = []
        change = False

        # vxprint change
        for block in self.vxprint().split('\n\n'):
            for line in block.split('\n')[:-1]:
                if not change:
                    lines.append(line)
                    if name in line and name == line.split()[1]:
                        change = True
                        continue
                    else:
                        break
                sp = line.split()
                if sp[4].isdigit():
                    sp[4] = str(Size(size).half_k_blocks)
                lines.append(' '.join(sp))
            change = False
        # the extra '\n' is needed or else the next time the first line will
        # get appended right after the last, without a new line.
        self.resources.fs.write('vxprint', '\n'.join(lines) + '\n')

    def properties(self, name):
        if not self.exists(name=name):
            raise NasExecCommandException('%s fs ERROR V-288-646 '
                    'File system %s does not exist.' % (self.type, name))
        kwargs = self.get_entry_kwargs(name=name)
        if name == FILESYSTEM_RESTORE_STILL_RUNNING:
            kwargs['rollsync_status'] = ROLLSYNC_STATUS_RUNNING % name
        else:
            kwargs['rollsync_status'] = ROLLSYNC_STATUS_NOT_RUNNING
        return FS_PROPERTIES_TEMPLATE % kwargs


class SfsMockDbShare(BaseMockDbShare):
    """ Database that mocks the information related to the SFS shares.
    """
    name = "share"
    type = 'SFS'
    identifier = ("name", "client")
    display_line = "%(name)s %(client)s (%(options)s)"
    display_regex = ShareResource.display_regex
    regexes = dict(
        list=re.compile(r"^nfs\s+share\s+show$"),
        insert=re.compile(r"^nfs\s+share\s+add\s+(?P<options>[\w,]+)\s+"
                          r"(?P<name>[/\w-]+)\s+(?P<client>[\w\.\*]+)$"),
        delete=re.compile(r"^nfs\s+share\s+delete\s+(?P<name>[/\w-]+)\s+"
                          r"(?P<client>[\w\.\*]+)$")
    )
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "nfs share show")
    )
    already_exists_msg = ""
    faulted_shares = FAULTED_SHARES

    def before_insert(self, **kwargs):
        """ Overrides the base method to do some actions before insert data
        into the SFS Mock database json. Basically simulates the validation
        messages done in real SFS server, throwing NasExecCommandException
        to be caught in the main methods of NAS resources (such as list, get,
        exists, create, delete, resize, etc) after calling the execute()
        method.
        """
        path = kwargs['name']
        if self.exists(**kwargs):
            # if already exists, just updates the options in SFS.
            # SFS has this behavior while adding a share, it just shows a
            # warning message saying that the options were changed.
            self.update(**kwargs)
            raise StopInsertException('Share update due to %s behavior'
                                      % self.type)
        for line in self.resources.fs.list().splitlines():
            match = SfsMockDbFilesystem.match_display_regex(line)
            if not match:
                continue
            fs = match.groupdict()['name']
            if path.split('/')[-1] == fs:
                return
        raise NasExecCommandException("fs for share %s doesn't exist" % path)

    def list(self):
        """ This method is overridden to includes a 'fake' Faulted Shares in
        the output display, like it occurs in SFS list display.
        """
        str_data = super(SfsMockDbShare, self).list()
        str_data = '%s\n\nFaulted Shares:\n%s' % (str_data,
                                                '\n'.join(self.faulted_shares))
        return str_data


class SfsMockDbDisk(BaseMockDbDisk):
    """ Database that mocks the information related to the SFS disks.
    """
    name = "disk"
    identifier = "name"
    display_line = "%(name)s - -"
    display_regex = DiskResource.display_regex
    regexes = dict(
        list=re.compile(r"^storage\s+disk\s+list$"),
        insert=None,
        delete=None
    )
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage disk list")
    )


class SfsMockDbPool(BaseMockDbPool):
    """ Database that mocks the information related to the SFS pools.
    """
    name = "pool"
    identifier = "name"
    display_line = "%(name)s - -"
    display_regex = PoolResource.display_regex
    regexes = dict(
        list=re.compile(r"^storage\s+pool\s+list$"),
        insert=None,
        delete=None
    )
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage pool list")
    )


class SfsMockDbSnapshot(BaseMockDbSnapshot):
    """ Database that mocks the information related to the SFS pools.
    """
    name = "snapshot"
    type = 'SFS'
    identifier = "name"
    display_line = "%(name)s spaceopt %(filesystem)s 2015/04/08 16:11"
    display_regex = SnapshotResource.display_regex
    cache_display_regex = CacheResource.display_regex
    filesystem_match_display_regex = SfsMockDbFilesystem.match_display_regex
    regexes = dict(
        list=re.compile(r"^storage\s+rollback\s+list$"),
        insert=re.compile(r"^storage\s+rollback\s+create\s+space-optimized\s+"
                          r"(?P<name>[\w-]+)\s+(?P<filesystem>[\w-]+)\s+"
                          r"(?P<cache>[\w-]+)$"),
        delete=re.compile(r"^storage\s+rollback\s+destroy\s+"
                          r"(?P<name>[\w-]+)\s+(?P<filesystem>[\w-]+)$"),
        restore=re.compile(r"^storage\s+rollback\s+restore\s+(?P<filesystem>"
                           r"[\w-]+)\s+(?P<name>[\w-]+)$"),
        offline=re.compile(r"^storage\s+rollback\s+offline\s+(?P<name>[\w-]+)"
                           r"$"),
        online=re.compile(r"^storage\s+rollback\s+online\s+(?P<name>[\w-]+)$"),
    )

    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage rollback list"),
        cache=GetCacheSnapshotsForObjects(),
    )

    already_exists_msg = (type + " rollback ERROR V-288-2026 Rollback %(name)s"
                           " already exist for file system %(filesystem)s.")
    fs_does_not_exist_msg = (type + " rollback ERROR V-288-758 File system "
                             "%(filesystem)s does not exist.")
    co_does_not_exist_msg = (type + " rollback ERROR V-288-1768 cache object "
                             "%(cache)s does not exist. Create with "
                             "<rollback cache create>")
    snap_does_not_exist_msg = (type + " rollback ERROR V-288-2028 Rollback "
                               "%(name)s does not exist for file "
                               "system %(filesystem)s.")
    snap_does_not_exist_restore_msg = (type + " rollback ERROR V-288-2029 "
                                       "Rollback %(name)s does not exist for "
                                       "file system %(filesystem)s.")
    fs_does_not_exist_restore_msg = (type + " rollback ERROR V-288-1430 File "
                                     "system %s does not exist.")
    restore_failed1_msg = (type + " rollback ERROR V-288-2022 restore from "
                           "rollback %s failed.")
    restore_failed2_msg = (type + " rollback ERROR V-288-2236 Unable to "
                                  "restore file system %s with rollback %s.")
    destroy_failed_online_msg = (type + " rollback ERROR V-288-2023 Rollback "
                                "destroy operation failed as %(name)s is in "
                                "online state, run offline first")
    already_offline_msg = (type + " fs ERROR V-288-843 Filesystem is already "
                           "offline.")
    already_online_msg = (type + " fs INFO V-288-1878 Filesystem is already "
                          "online on master node, trying to mount on all the "
                          "nodes.")

    fsck_failed_message = (type + " rollback ERROR V-288-1883 fsck failed for "
                           "%(name)s.")

    rollback_running_msg = (type + " rollback ERROR V-288-2027 Rollback "
                            "%(name)s dissociate failed.")

    def before_insert(self, **kwargs):
        """ Overrides the base method to do some actions before insert data
        into the SFS Mock database json. Basically simulates the validation
        messages done in real SFS server, throwing NasExecCommandException
        to be caught in the main methods of NAS resources (such as list, get,
        exists, create, delete, resize, etc) after calling the execute()
        method.
        """
        self._test_cache(**kwargs)
        self._test_filesystem(**kwargs)
        line = self.resources.cache.get(name=kwargs['cache'])
        cache_data = self.resources.cache.display_regex.match(line).groupdict()
        if not int(cache_data['available']):
            raise NasExecCommandException(self.fsck_failed_message % kwargs)

        # any generic error
        if kwargs['name'] == ANY_GENERIC_ERROR:
            raise NasExecCommandException("Any generic error message")

    def after_insert(self, **kwargs):
        """ Overrides the base method to do some actions after insert data
        into the SFS Mock database json. Basically just adds a new entry in the
        ['snapshot']['cache'] json data to associate caches to snapshots as
        they are not being displayed in the list and there's no way to
        associate them. The only way to associate them is by the output of the
        command "storage rollback cache list <CACHE_NAME>", and by saving the
        data in the mock json database, it can be retrieved later by
        simulating that mentioned command. Please refer to the
        SfsMockDbCache.list_snapshots method for better understanding.
        """
        caches = self.resources.snapshot.read('cache')
        caches.setdefault(kwargs['cache'], [])
        caches[kwargs['cache']].append(kwargs['name'])
        filesystem = self._get_filesystem_by_rollback_name(kwargs['name'])
        filesystem['name'] = kwargs['name']
        filesystem['size'] = "%s%s" % re.match(r'(\d+)[\.]{0,1}\d+([KMGT])',
                                               filesystem['size']).groups()
        self.resources.fs.insert(**filesystem)
        self.resources.fs.offline(filesystem['name'])

    def before_delete(self, **kwargs):
        """ Overrides the base method to do some actions before delete data
        from the SFS Mock database json. Basically raises validation errors
        messages, just simulating potential errors in SFS server.
        """
        # any generic error
        if kwargs['name'] == ANY_GENERIC_ERROR:
            raise NasExecCommandException("Any generic error message")
        if kwargs['filesystem'] == FILESYSTEM_RESTORE_STILL_RUNNING:
            raise NasExecCommandException(self.rollback_running_msg % kwargs)
        if kwargs['name'] == FORCE_ERROR_OFFLINE:
            raise NasExecCommandException(self.destroy_failed_online_msg
                                          % kwargs)
        for line in self.resources.fs.list().splitlines():
            match = SfsMockDbFilesystem.match_display_regex(line)
            data = match.groupdict() if match else {}
            if data and data['name'] == kwargs['name'] and \
               data['online'] == 'online':
                raise NasExecCommandException(self.destroy_failed_online_msg
                                              % kwargs)
        self._test_filesystem(**kwargs)
        self._test_snapshot(**kwargs)

    def after_delete(self, **kwargs):
        """ Removes the file system entry after removing snapshot.
        """
        name = kwargs['name']
        self.resources.fs.delete(name=name)
        caches = self.resources.snapshot.read('cache')
        for cache, snapshots in caches.items():
            if name in snapshots:
                caches[cache].remove(name)

    def _test_cache(self, **kwargs):
        """ Validation used in before_insert method to check the existence of
        a cache, simulating an error message like in SFS server.
        """
        cache = kwargs['cache']
        for line in self.resources.cache.list().splitlines():
            match = self.cache_display_regex.match(line)
            if not match:
                continue
            if match.groupdict()['name'] == cache:
                return
        raise NasExecCommandException(self.co_does_not_exist_msg %
                                      kwargs)

    def _test_filesystem(self, **kwargs):
        """ Validation used in before_insert and before_delete methods to check
        the existence of a file system, simulating an error message like in
        SFS server.
        """
        filesystem = kwargs['filesystem']
        for line in self.resources.fs.list().splitlines():
            match = self.filesystem_match_display_regex(line)
            if not match:
                continue
            data = match.groupdict()
            if data['name'] == filesystem:
                return
        raise NasExecCommandException(self.fs_does_not_exist_msg %
                                      kwargs)

    def _test_snapshot(self, **kwargs):
        """ Validation used in before_delete method to check the existence of
        a snapshot, simulating an error message like in SFS server.
        """
        snap = kwargs['name']
        for line in self.resources.snapshot.list().splitlines():
            match = SfsMockDbSnapshot.display_regex.match(line)
            if not match:
                continue
            if match.groupdict()['name'] == snap:
                return
        raise NasExecCommandException(self.snap_does_not_exist_msg %
                                      kwargs)

    def restore(self, name, filesystem):
        """ Mocks the rollback restore action by raising the proper error
        messages.
        """
        if ANY_GENERIC_ERROR in name:
            raise NasExecCommandException("Any generic error message")
        if not self.exists(name=name) and \
           name != FORCE_FS_BECOME_ONLINE_AFTER_RESTORE:
            raise NasExecCommandException(self.snap_does_not_exist_restore_msg
                                      % dict(name=name, filesystem=filesystem))
        if not self.resources.fs.exists(name=filesystem) and \
           filesystem != FORCE_ERROR_ONLINE:
            raise NasExecCommandException(self.fs_does_not_exist_restore_msg %
                                          filesystem)
        if name == FORCE_FS_BECOME_ONLINE_AFTER_RESTORE:
            self.resources.fs.online(filesystem)

        if filesystem == FILESYSTEM_FORCE_RESTORE_FAIL or \
           filesystem == FILESYSTEM_RESTORE_STILL_RUNNING:
            msg = "%s\n%s" % (self.restore_failed1_msg % name,
                              self.restore_failed2_msg % (filesystem, name))
            raise NasExecCommandException(msg)

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
                return match.groupdict()

    def offline(self, name):
        """ Modifies the fs database changing the 'online' column entry to
        'offline' value. It also checks whether the file system has or not
        any shares underneath, raising the proper error message.
        """
        if name == FORCE_ERROR_OFFLINE:
            raise NasExecCommandException("Any generic error message while "
                                          "trying to bring fs offline")
        exc = NasExecCommandException(self.already_offline_msg)
        self.resources.fs.update(exception_if_the_same=exc, name=name,
                                 online='offline')

    def online(self, name):
        """ Modifies the fs database changing the 'online' column entry to
        'offline' value.
        """
        exc = NasExecCommandException(self.already_online_msg)
        self.resources.fs.update(exception_if_the_same=exc, name=name,
                                 online='online')


class SfsMockDbCache(BaseMockDbCache):
    """ Database that mocks the information related to the SFS caches.
    """
    name = "cache"
    type = 'SFS'
    identifier = "name"
    display_line = "%(name)s %(size)s %(used)s (0) %(available)s " \
                   "(0) 0"
    display_regex = CacheResource.display_regex
    regexes = dict(
        list=re.compile(r"^storage\s+rollback\s+cache\s+list$"),
        insert=re.compile(r"^storage\s+rollback\s+cache\s+create\s+"
                          r"(?P<name>[\w-]+)\s+(?P<size>\d+[kmgtKGMT]{1})\s+"
                          r"(?P<pool>[-\w]+)$"),
        delete=re.compile(r"^storage\s+rollback\s+cache\s+destroy\s+"
                          r"(?P<name>[\w-]+)$"),
        vxcache_growcacheto=re.compile(r"^vxcache\s+growcacheto\s+"
                                       r"(?P<name>[\w-]+)\s+"
                                       r"(?P<size>\d+[kmgtKGMT]{1})$"),
        list_snapshots=re.compile(r"^storage\s+rollback\s+cache\s+list"
                                  r"\s+(?P<name>[\w-]+)$"),
    )
    commands_for_mock_db = dict(
        list=CommandMockDb(CLISH % "storage rollback cache list"),
    )

    already_exists_msg = type + " rollback ERROR V-288-2339 Cache object " \
                         "%(name)s already exists."
    does_not_exist_msg = type + " rollback ERROR V-288-1765 cache object " \
                         "%(name)s does not exist."
    is_in_use_msg = type + " rollback ERROR V-288-1766 cache object" \
                           " %(name)s is in use."
    pool_does_not_exist_msg = type + " rollback ERROR V-288-678 Pool(s) or " \
                              "disk(s) %(pool)s does not exist."
    start_cache_error_msg = type + " rollback ERROR V-288-2053 Start of " \
                                   "cache object %(name)s failed."
    insufficient_space_msg = type + " rollback ERROR V-288-921 Unable to " \
                        "create fs %(name)s due to either insufficient " \
                        "space/unavailable disk. Please run scanbus."
    cannot_allocate_space_msg = "VxVM vxassist ERROR V-5-1-436 Cannot " \
        "allocate space to grow volume to %s blocks"

    size_digit = re.compile(r"^(\d+)[kmgtKGMT]{1}$")

    def prepare_insert_kwargs(self, **kwargs):
        """ Prepare the kwargs before uses it to insert in the Mock db.
        Basically converts the the size into mega bytes and just retrieves
        the digit without the unit, as the SFS server displays only the number
        of megas in "storage rollback cache list" command.
        """
        megas = str(Size(kwargs['size']).megas)
        kwargs['size'] = Decimal(self.size_digit.match(megas).groups()[0])
        self._generate_used_available_space(kwargs)
        return kwargs

    def _generate_used_available_space(self, kwargs):
        """ Updates the kwargs including the keys "used" and "available"
        generating a value of 1/20 of the current size as the used space.
        """
        rup = lambda x: x.quantize(Decimal('1.'), rounding=ROUND_UP)
        size = kwargs.get('size')
        if size:
            if 'used' not in kwargs:
                kwargs['used'] = rup(size / 20)
            if 'available' not in kwargs:
                kwargs['available'] = rup(size - kwargs['used'])

    def update(self, *args, **kwargs):
        """ Just overrides it to include information about "used" and
        "available" in the update.
        """
        self._generate_used_available_space(kwargs)
        super(SfsMockDbCache, self).update(*args, **kwargs)

    def vxcache_growcacheto(self, name, size):
        """ Simulates the command 'vxcache growcacheto', increasing the size
        of a cache. It raises proper validation message like in SFS server
        if the size is too big.
        """
        if Size(size) >= Size('99999T'):
            raise VxCommandsException(
                     self.cannot_allocate_space_msg % Size(size).half_k_blocks)
        self.update(name=name, size=Size(size).megas.digit)

    def list_snapshots(self, name):
        """ Simulates the list of snapshots given a cache name, providing
        likely the same output as SFS does executing the command
        "storage rollback cache list <CACHE_NAME>". Please refer to the
        SfsMockDbSnapshot.after_insert method for better understanding.
        """
        caches = self.resources.snapshot.read('cache')
        snapshots = caches.get(name, [])
        result = "\nrollbacks located on cache {0}:\n{1}".format(
                                                    name, '\n'.join(snapshots))
        return result

    def before_insert(self, **kwargs):
        """ Overrides the base method to do some actions before insert data
        into the SFS Mock database json. Basically simulates the validation
        messages done in real SFS server, throwing NasExecCommandException
        to be caught in the main methods of NAS resources (such as list, get,
        exists, create, delete, resize, etc) after calling the execute()
        method.
        """

        # test pool
        pool = kwargs['pool']
        invalid_pool = True
        for line in self.resources.pool.list().splitlines():
            match = SfsMockDbPool.display_regex.match(line)
            if not match:
                continue
            if match.groupdict()['name'] == pool:
                invalid_pool = False
                break
        if invalid_pool:
            raise NasExecCommandException(self.pool_does_not_exist_msg %
                                          kwargs)

        # test size
        size = Size('%sM' % kwargs['size'])
        # (Rogerio Hilbert): actually should be less than 5 according to
        # my tests on SFS. I'm using 6 here to test a potential unexpected
        # behavior from SFS though.
        if size < Size('6M'):
            raise NasExecCommandException(self.start_cache_error_msg % kwargs)
        if size >= Size("99999T"):
            raise NasExecCommandException(self.insufficient_space_msg %
                                          kwargs)

        # any generic error
        if kwargs['name'] == ANY_GENERIC_ERROR:
            raise NasExecCommandException("Any generic error message")

    def after_insert(self, **kwargs):
        """ Overrides the base method to do some actions after insert data
        into the SFS Mock database json. Inserts new data entry in the
        'vxprint' db json, like SFS does by creating new cache object, thus
        it will be available for display by the 'vxprint' command.
        """
        # includes an entry in vxdisk_listtag related to this related to the
        # cache object.
        entry = "emc_clariion0_110   site   %(pool)s" % kwargs
        self.resources.fs.write('vxdisk_listtag', entry)
        size = Size('%sM' % kwargs['size'])
        size = Size(size)
        num_bytes = size.num_bytes
        blocks_size = num_bytes / 512
        kwargs['size'] = blocks_size
        vxprint = """


co %(name)s  -            ENABLED  -        -        ACTIVE   -       -
v  %(name)s_tier1 %(name)s ENABLED %(size)s -      ACTIVE   -       -
pl %(name)s_tier1-01 %(name)s_tier1 ENABLED %(size)s - ACTIVE -     -
sd emc_clariion0_110-28 %(name)s_tier1-01 ENABLED %(size)s 0 - -      - sda


        """ % kwargs
        self.resources.fs.write('vxprint', vxprint)

    def before_delete(self, **kwargs):
        """ Before deleting a cache, checks if the name is ANY_GENERIC_ERROR
        and raises a NasExecCommandException to simulate a failure.
        """
        cache = kwargs['name']

        # any generic error
        if cache == ANY_GENERIC_ERROR:
            raise NasExecCommandException("Any generic error message")

        # check whether is in use or not
        caches = self.resources.snapshot.read('cache')
        if caches.get(cache):
            raise NasExecCommandException(self.is_in_use_msg % kwargs)

        # check_existence
        for line in self.list().splitlines():
            match = self.match_display_regex(line)
            if not match:
                continue
            if match.groupdict()['name'] == cache:
                return
        raise NasExecCommandException(self.does_not_exist_msg % kwargs)

    def make_cache_full(self, cache):
        """ Makes the cache object become full.
        """
        line = self.get(name=cache)
        data = self.match_display_regex(line).groupdict()
        self.update(name=cache, available="0", used=str(data['size']))
