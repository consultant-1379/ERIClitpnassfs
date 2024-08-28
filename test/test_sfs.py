##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=E1101
""" This module contains basically unit tests.
"""

import mock
import re
import unittest
import base64
from paramiko.rsakey import RSAKey

from paramiko import SSHException

from NASStringIO import NASStringIO as StringIO
from naslib import NasDrivers
from naslib.nasexceptions import NasExecCommandException, NasException, \
    NasExecutionTimeoutException, NasBadPrivilegesException, \
    NasBadUserException, NasDriverDoesNotExist, NasConnectionException, \
    NasUnexpectedOutputException, NasIncompleteParsedInformation
from naslib.objects import Pool, FileSystem, Disk, Share, Cache, Snapshot
from naslib.resourceprops import StringOptions, Size
from naslib.drivers.sfs.resources import ShareResource
from naslib.drivers.sfs.resourceprops import SfsSize
from naslib.drivers.sfs.sfsmock.db import SfsMockDb
from naslib.drivers.sfs.sfsmock.main import SfsMock
from naslib.drivers.sfs.sfsmock.dbresources import SfsMockDbFilesystem,\
    SfsMockDbCache, SfsMockDbSnapshot, ANY_GENERIC_ERROR, get_faulted_shares, \
    FORCE_ERROR_ONLINE, FORCE_FS_BECOME_ONLINE_AFTER_RESTORE, \
    FORCE_ERROR_OFFLINE, ANY_ERROR_FOR_FS_RESIZE, \
    FILESYSTEM_RESTORE_STILL_RUNNING, FILESYSTEM_FORCE_RESTORE_FAIL, \
    FORCE_ERROR_OFFLINE, ANY_ERROR_FOR_FS_RESIZE
from naslib.drivers.sfs.utils import VxCommands, VxCommandsException
from naslib.nasmock.mockexceptions import MockException
from naslib.nasmock.connection import NasConnectionMock
from naslib.nasmock.ssh import SshClientMock
from naslib.ssh import SSHClient
from naslib.paramikopatch import PatchedTransport, AutoAddPolicy, \
                  PatchedBadHostKeyException, SSHClient as ParamikoSSHClient, \
                  PatchedHostKeys

class TestSfsDb(unittest.TestCase):
    def setUp(self):
        self.driver_name = 'Sfs'
        self.type = "SFS"
        self.extra_hard_coded_option = ""
        self.incomplete_cache_out = """
CACHE NAME                      TOTAL(Mb)   USED(Mb) (%)    AVAIL(Mb) (%)    SDCNT
CI15_cache1                            25          4 (16)         21 (84)       1
68Cache1                               40          4 (10)         36 (90)       1
ST51-cache                              -          -    -          -    -       -
105cache1                            1104          5  (0)       1099 (99)       0
ST66_cashe                            360          5  (1)        355 (98)       2
"""

    def test_mock_data(self):
        db = SfsMockDb()
        self.assertTrue('disk' in db.data)
        self.assertTrue('pool' in db.data)
        self.assertTrue('fs' in db.data)
        self.assertTrue('share' in db.data)

        ssh = SshClientMock("host", "user", "password", mock_db=db)
        ssh.connect()
        out = ssh.run("storage disk list")[1]
        clean = lambda x: '\n'.join([i.strip() for i in x.splitlines()
                                               if i.strip()])
        self.assertEquals(out, clean(db.data['disk']['list']))
        out = ssh.run("storage pool list")[1]
        self.assertEquals(out, clean(db.data['pool']['list']))
        out = ssh.run("storage fs list")[1]
        self.assertEquals(out, clean(db.data['fs']['list']))
        out = ssh.run("nfs share show")[1]
        out = out.split(ShareResource.faulted_delimiter)[0].strip()
        self.assertEquals(out, clean(db.data['share']['list']))

    def _test_sfs(self, s):
        # testing get method for pool resource
        pools = s.pool.list()
        self.assertTrue(len(pools) > 0)
        self.assertTrue(hasattr(pools[0], 'name'))
        self.assertEquals(pools[0], s.pool.get(pools[0].name))

        # testing get method for disk resource
        disks = s.disk.list()
        self.assertTrue(len(disks) > 0)
        self.assertTrue(hasattr(disks[0], 'name'))
        self.assertEquals(disks[0], s.disk.get(disks[0].name))

        # testing get method for filesystem resource
        filesystems = s.filesystem.list()
        self.assertTrue(len(filesystems) > 0)
        self.assertTrue(hasattr(filesystems[0], 'name'))
        self.assertTrue(hasattr(filesystems[0], 'size'))
        self.assertTrue(hasattr(filesystems[0], 'pool'))
        self.assertTrue(isinstance(filesystems[0].pool, Pool))
        self.assertEquals(filesystems[0],
                          s.filesystem.get(filesystems[0].name))
        # testing exist method for file system resource
        self.assertTrue(s.filesystem.exists(filesystems[0].name))
        self.assertFalse(s.filesystem.exists("another_name"))

        # testing get method for share resource
        shares = s.share.list()
        self.assertTrue(len(shares) > 0)
        self.assertTrue(hasattr(shares[0], 'name'))
        self.assertTrue(hasattr(shares[0], 'options'))
        self.assertTrue(hasattr(shares[0], 'client'))
        self.assertEquals(shares[0], s.share.get(shares[0].name,
                                                 shares[0].client))

        # testing exist method for share resource
        self.assertTrue(s.share.exists(shares[0].name, shares[0].client))
        self.assertFalse(s.share.exists("name", "another_client"))
        self.assertFalse(s.share.exists("another_name", "another_client"))
        self.assertFalse(s.share.exists("another_name", "client"))
        # testing create method for file system resource
        name, size, pool = "some_fs", "11008K", "SFS_Pool"
        new_fs = s.filesystem.create(name, size, pool)
        self.assertTrue(hasattr(new_fs, 'name'))
        self.assertTrue(hasattr(new_fs, 'size'))
        self.assertTrue(hasattr(new_fs, 'pool'))
        self.assertEquals(new_fs.name, name)
        self.assertEquals(new_fs.size, Size(size))
        self.assertTrue(isinstance(new_fs.pool, Pool))
        self.assertEquals(new_fs.pool.name, pool)
        self.assertEquals(new_fs, s.filesystem.get(new_fs.name))
        self.assertTrue(new_fs in s.filesystem.list())
        self.assertEquals(repr(new_fs),
                          "<%sFileSystem some_fs>" % self.driver_name)

        # tests double creation of a fs
        self.assertRaises(FileSystem.AlreadyExists, s.filesystem.create,
                          name, '20M', pool)

        # tests create fs with an invalid pool
        self.assertRaises(Pool.DoesNotExist, s.filesystem.create,
                          'some_other', size, "invalid_pool")

        # tests create fs with wrong size
        self.assertRaises(FileSystem.SizeException, s.filesystem.create, name,
                          '20J', pool)

        # tests create fs with wrong layout
        self.assertRaises(NasException, s.filesystem.create, name, '20M',
                          pool, layout="wrong_layout")

        # tests create fs with a huge size amount
        self.assertRaises(FileSystem.InsufficientSpaceException,
                          s.filesystem.create, "some_other",
                          '9999999T', pool, layout="simple")

        # tests create fs with a huge size amount
        self.assertRaises(FileSystem.CreationException,
                          s.filesystem.create, ANY_GENERIC_ERROR,
                          '1T', pool, layout="simple")

        # tests fs resizing
        # try to resize with a invalid size unit
        self.assertRaises(FileSystem.SizeException, new_fs.resize, '50Q', pool)


        # success path with the pool name as argument
        new_fs.resize('60M', 'SFS_Pool')
        self.assertEquals(new_fs.size, Size('60M'))
        self.assertEquals(s.filesystem.get(new_fs.name).size, Size('60M'))

        # success path without the pool name as arguments
        new_fs.resize('80M')
        self.assertEquals(s.filesystem.get(new_fs.name).size, Size('80M'))

        # success path with file system with usage over 95%
        new_fs.resize('99950G', 'SFS_Pool')
        # try to resize giving huge size
        self.assertRaises(FileSystem.InsufficientSpaceException, new_fs.resize,
                          '9999999T')

        # try to resize offline file system
        s.filesystem.online(new_fs.name, False)
        self.assertFalse(s.filesystem.get(new_fs.name).online)
        self.assertRaises(FileSystem.ResizeException, s.filesystem.resize,
                          new_fs.name, '200M')
        self.assertFalse(s.filesystem.get(new_fs.name).online)

        # fail onlining the file system when resizing
        fs = s.filesystem.create(FORCE_ERROR_ONLINE, '50M', 'SFS_Pool')
        s.filesystem.online(fs.name, False)
        self.assertFalse(s.filesystem.get(fs.name).online)
        self.assertRaises(FileSystem.ResizeException, s.filesystem.resize,
                          fs.name, '100M')

        # testing any generic error
        fs = s.filesystem.create(ANY_ERROR_FOR_FS_RESIZE, '50M', 'SFS_Pool')
        self.assertRaises(FileSystem.ResizeException, s.filesystem.resize,
                          fs.name, '200M')

        # try to resize giving the same size
        s.filesystem.online(new_fs.name, True)
        self.assertTrue(s.filesystem.get(new_fs.name).online)
        self.assertRaises(FileSystem.SameSizeException,
                          s.filesystem.resize, new_fs.name, '80M', pool)

        # try to shrink
        self.assertRaises(FileSystem.CannotShrinkException,
                          s.filesystem.resize, name, "118K", pool)


        # testing delete method for file system resource
        new_fs.delete()
        self.assertTrue(new_fs not in s.filesystem.list())

        # tests deletion of a fs that doesn't exist
        self.assertRaises(FileSystem.DeletionException, new_fs.delete)

        # tests creation of a share with fs deleted
        path, options, client = "/vx/some_fs", "ro", "1.1.1.1"
        self.assertRaises(Share.CreationException, s.share.create,
                          name, client, options)

        # create the file system again
        fs = s.filesystem.create(name, size, pool)

        # get properties of a file system
        properties = s.filesystem._properties(name)
        self.assertTrue(isinstance(properties, dict))
        self.assertEquals(properties.get('Layout'), fs.layout)
        self.assertEquals(Size(properties.get('Size', '0K')), fs.size)
        self.assertEquals(properties.get('Rollsync Status'), 'Not Running')

        # testing create method for share resource
        new_share = s.share.create(path, client, options)
        self.assertTrue(hasattr(new_share, 'name'))
        self.assertTrue(hasattr(new_share, 'client'))
        self.assertTrue(hasattr(new_share, 'options'))
        self.assertEquals(new_share.name, path)
        self.assertEquals(new_share.client, client)
        self.assertEquals(new_share.options,
                          StringOptions(options +
                                    (",%s" % self.extra_hard_coded_option
                                     if self.extra_hard_coded_option else "")))
        self.assertEquals(new_share, s.share.get(new_share.name,
                                                 new_share.client))
        self.assertTrue(new_share in s.share.list())

        length = len(s.share.list())
        # tests double creation of a share (must pass, and the length list
        # must be the same as well)
        s.share.create(path, client, options)
        self.assertEquals(len(s.share.list()), length)

        # check for the share options update
        sh1 = s.share.get(path, client)
        self.assertEquals(sh1.options,
                          StringOptions(options +
                                    (",%s" % self.extra_hard_coded_option
                                     if self.extra_hard_coded_option else "")))
        s.share.create(path, client, "rw,no_root_squash")
        sh2 = s.share.get(path, client)
        self.assertEquals(sh2.options,
                          StringOptions("rw,no_root_squash" +
                                    (",%s" % self.extra_hard_coded_option
                                     if self.extra_hard_coded_option else "")))

        # testing delete method for share resource
        new_share.delete()
        self.assertTrue(new_share not in s.share.list())

        # tests deletion of a share that doesn't exist
        self.assertRaises(Share.DeletionException, new_share.delete)

        # tests getting a share that doesn't exist
        self.assertRaises(Share.DoesNotExist, s.share.get,
                          'some_invalid_path', 'invalid_client')

        # tests getting a fs that doesn't exist
        self.assertRaises(FileSystem.DoesNotExist, s.filesystem.get,
                          'some_invalid_fs')

        # testing exist method for disk resource
        self.assertTrue(s.disk.exists(disks[0].name))
        self.assertFalse(s.disk.exists("another_name"))

        # tests getting a disk that doesn't exist
        self.assertRaises(Disk.DoesNotExist, s.disk.get,
                          'some_invalid_disk')

        # testing exist method for pool resource
        self.assertTrue(s.pool.exists(pools[0].name))
        self.assertFalse(s.pool.exists("another_name"))

        # tests getting a pool that doesn't exist
        self.assertRaises(Pool.DoesNotExist, s.pool.get,
                          'some_invalid_pool')

        ssh_run = s.ssh.run
        s.ssh.run = lambda cmd, timeout: (0, "output", "error")
        self.assertRaises(NasExecCommandException, s.execute,
                          "invalid command")
        s.ssh.run = ssh_run
        self.assertRaises(NotImplementedError, s.disk.create)
        self.assertRaises(NotImplementedError, s.disk.delete)
        self.assertRaises(NotImplementedError, s.pool.create)
        self.assertRaises(NotImplementedError, s.pool.delete)
        share = Share(s.share, '/vx/path', '1.1.1.1', 'rw,no_root_squash')
        other = Share(s.share, '/vx/path', '1.1.1.1', 'rw,no_root_squash')
        self.assertEquals(str(share.options), 'rw,no_root_squash')
        self.assertEquals(str(other.options), 'rw,no_root_squash')
        self.assertEquals(share, other)
        self.assertTrue(share == other)
        self.assertTrue(share.diff(other) == {})
        self.assertFalse(share != other)
        self.assertEquals(repr(share), "<Share /vx/path 1.1.1.1>")
        other = Share(s.share, '/vx/path', '1.1.1.1', 'rw')
        self.assertEquals(str(other.options), 'rw')
        self.assertNotEquals(share, other)
        self.assertTrue(share != other)
        self.assertFalse(share == other)
        self.assertEquals(share.diff_display(other),
                          'options: "rw,no_root_squash" != "rw"')

    def _test_sfs_size_comparison(self, s):

        pool = "SFS_Pool"
        # testing some comparison of SFS sizes
        fs_10_75m = s.filesystem.create("fs_10_75m", '11008k', pool)
        self.assertTrue(SfsSize(22016, '10.75m', fs_10_75m) ==
                        Size('11001k'))
        fs_1_g = s.filesystem.create("fs_101_giga", '1058816k', pool)
        self.assertTrue(SfsSize(2117632, '1.00G', fs_1_g) ==
                        Size('1058816k'))
        fs_1_g_2 = s.filesystem.create("fs_101_giga_2", '1058811k', pool)
        self.assertTrue(SfsSize(2117632, '1.00G', fs_1_g_2) ==
                        Size('1058811k'))
        for i in xrange(1, 9):
            self.assertTrue(SfsSize(22016, '10.75m', fs_10_75m) ==
                            Size('1100%sk' % i))
        self.assertFalse(SfsSize(22016, '10.75m', fs_10_75m) ==
                         Size('1.00G'))

    def _assert_cache_attributes(self, cache):
        self.assertTrue(hasattr(cache, 'name'))
        self.assertTrue(hasattr(cache, 'size'))
        self.assertTrue(hasattr(cache, 'pool'))
        self.assertTrue(hasattr(cache, 'used'))
        self.assertTrue(hasattr(cache, 'available'))
        self.assertTrue(hasattr(cache, 'used_percentage'))
        self.assertTrue(hasattr(cache, 'available_percentage'))
        self.assertTrue(hasattr(cache, 'snapshot_count'))

    def test_cache(self):
        mock_args = "10.44.86.226", "support", "support"
        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            caches = s.cache.list()
            length = len(caches)
            self.assertTrue(length > 0)
            cache = caches[0]
            self._assert_cache_attributes(cache)
            cache2 = Cache(s.cache, cache.name, cache.size, 'SFS_Pool')
            self.assertEquals(cache.pool.name, 'SFS_Pool')
            self.assertEquals(cache, cache2)
            self.assertEquals(cache.diff(cache2), cache2.diff(cache))
            self.assertEquals(cache, s.cache.get(cache.name))
            self.assertTrue(s.cache.exists(cache.name))
            for i, cache1 in enumerate(caches):
                for j, cache2 in enumerate(caches):
                    if i == j:
                        continue
                    self.assertNotEquals(cache1, cache2)
            self.assertFalse(s.cache.exists('mycache'))
            new_cache = s.cache.create('mycache', '20M', 'SFS_Pool')
            self._assert_cache_attributes(new_cache)
            caches = s.cache.list()
            self.assertTrue(new_cache in caches)
            self.assertEquals(new_cache, s.cache.get('mycache'))
            self.assertTrue(s.cache.exists('mycache'))
            self.assertFalse(s.cache.exists('any'))
            for c in caches:
                self.assertEquals(c.used_percentage + c.available_percentage,
                                  100)

            self.assertRaises(Cache.DoesNotExist, s.cache.get, 'any')
            self.assertRaises(TypeError, s.cache.get)
            self.assertRaises(TypeError, s.cache.get, 'aaa', 'bbb')
            self.assertRaises(TypeError, s.cache.get, wrong_argument='asdfasd')
            self.assertRaises(Cache.AlreadyExists, s.cache.create, 'mycache',
                              '20M', 'SFS_Pool')
            s.cache.delete('mycache')
            caches = s.cache.list()
            self.assertFalse(new_cache in caches)

            self.assertRaises(Cache.SizeException, s.cache.create, 'mycache',
                              '4M', 'SFS_Pool')

            # (Rogerio Hilbert): actually cache size should be less
            # than 5 according to my tests on SFS. I'm using 6M as the
            # minimum allowed size on SfsMock to test a potential
            # unexpected behavior from SFS though.
            self.assertRaises(Cache.CreationException, s.cache.create,
                              'mycache', '5M', 'SFS_Pool')

            self.assertRaises(Cache.SizeException, s.cache.create,
                              'mycache', '4W', 'SFS_Pool')

            self.assertRaises(Cache.InsufficientSpaceException, s.cache.create,
                              'mycache', '99999999T', 'SFS_Pool')

            self.assertRaises(Pool.DoesNotExist, s.cache.create, 'mycache',
                              '20M', 'wrong_pool')

            self.assertRaises(Cache.CreationException, s.cache.create,
                              ANY_GENERIC_ERROR, '20M', 'SFS_Pool')

            self.assertRaises(Cache.DeletionException, s.cache.delete,
                              ANY_GENERIC_ERROR)

            self.assertRaises(Cache.DoesNotExist, s.cache.delete,
                              "non_existent")

            another_cache = s.cache.create('another_cache', '50M', 'SFS_Pool')
            self.assertEquals(s.cache.get('another_cache').size, Size('50M'))
            another_cache.resize('60M')
            self.assertEquals(s.cache.get('another_cache').size, Size('60M'))

            # try to resize with a invalid size unit
            self.assertRaises(Cache.SizeException, another_cache.resize, '50Q')

            # try to shrink
            self.assertRaises(Cache.CannotShrinkException,
                              another_cache.resize, '50M')

            # try to resize giving the same size
            self.assertRaises(Cache.SameSizeException, another_cache.resize,
                              '60M')

            # try to resize giving huge size
            self.assertRaises(Cache.InsufficientSpaceException,
                              another_cache.resize, '9999999T')

        output = (SfsMockDbCache.regexes['vxcache_growcacheto'], "", "Error")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            some_cache = s.cache.create('some_cache', '50M', 'SFS_Pool')
            err = ''
            try:
                some_cache.resize('100M')
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, Cache.ResizeException))
            self.assertEquals(str(err), 'ERROR while trying to execute '
                        'command "vxcache growcacheto some_cache 100M": Error')

    def _assert_snapshot_attributes(self, snapshot):
        self.assertTrue(hasattr(snapshot, 'name'))
        self.assertTrue(hasattr(snapshot, 'filesystem'))
        self.assertTrue(hasattr(snapshot, 'cache'))
        self.assertTrue(hasattr(snapshot, 'snaptype'))
        self.assertTrue(hasattr(snapshot, 'date'))

    @mock.patch('naslib.drivers.sfs.resources.SnapshotResource.rollbackinfo')
    def test_snapshot(self, mock_check_rollback_info):
        mock_check_rollback_info.return_value=['NAME TYPE SNAPDATE CHANGED_DATA SYNCED_DATA' \
            ,'=============  ========  ================  =============  ============'\
            ,'Int23-int23-s spaceopt Int23-int23 2016/10/17 09:55']
        mock_args = "10.44.86.226", "support", "support"

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as con:
            snapshots = con.snapshot.list()
            self.assertTrue(len(snapshots) > 1)
            snapshot = snapshots[0]
            self._assert_snapshot_attributes(snapshot)
            snapinfo = con.snapshot.rollbackinfo(snapshot.name)
            self.assertTrue(snapshot.name in snapinfo[2])
            self.assertTrue('NAME TYPE SNAPDATE CHANGED_DATA SYNCED_DATA' in snapinfo[0])
            cache_name = str(snapshot.cache)
            cache = Cache(con.snapshot, cache_name, snapshot.cache.size,
                          snapshot.cache.pool.name)
            snapshot_cpy = Snapshot(con.snapshot, snapshot.name,
                                    snapshot.filesystem, cache,
                                    snapshot.snaptype, snapshot.date)
            self.assertEqual(snapshot, snapshot_cpy)
            self.assertEqual(snapshot, con.snapshot.get(snapshot.name))
            self.assertTrue(con.snapshot.exists(snapshot.name))
            self.assertFalse(con.snapshot.exists("non_existent"))
            # Testing creation of snapshot
            new_snap = con.snapshot.create("Int110-storadm-snap",
                                           "Int110-storadm", "Int110-cache")
            self._assert_snapshot_attributes(new_snap)
            snapshots = con.snapshot.list()
            self.assertTrue(new_snap in snapshots)
            self.assertEquals(new_snap,
                              con.snapshot.get('Int110-storadm-snap'))
            self.assertTrue(con.snapshot.exists('Int110-storadm-snap'))
            self.assertFalse(con.snapshot.exists('any'))
            self.assertRaises(Cache.DeletionException, con.cache.delete,
                              "Int110-cache")  # test deletion of cache if it's
                                               # already being used

            # tests snapshot restore with a file system shared
            self.assertRaises(FileSystem.OfflineException,
                              con.snapshot.restore,
                              'Int110-storadm-snap', "Int110-storadm")

            # delete shares before restore
            deleted_shares = []
            for share in con.share.list():
                if share.name.endswith("Int110-storadm"):
                    share.delete()
                    deleted_shares.append(share)

            # restore
            con.snapshot.restore('Int110-storadm-snap', "Int110-storadm")

            # restore forcing error
            self.assertRaises(Snapshot.RestoreException, con.snapshot.restore,
                              ANY_GENERIC_ERROR, "Int110-storadm")

            # restore again
            con.snapshot.restore('Int110-storadm-snap', "Int110-storadm")

            # restore invalid snapshot
            self.assertRaises(Snapshot.DoesNotExist, con.snapshot.restore,
                              "invalid", "Int110-storadm")

            # restore invalid file system
            self.assertRaises(FileSystem.DoesNotExist, con.snapshot.restore,
                              'Int110-storadm-snap', "invalid")

            # restore online already
            con.snapshot.restore(FORCE_FS_BECOME_ONLINE_AFTER_RESTORE,
                                 "Int110-storadm")

            # restore force error when going online
            self.assertRaises(FileSystem.OnlineException, con.snapshot.restore,
                              'Int110-storadm-snap', FORCE_ERROR_ONLINE)

            # restore fail and force error when going online and show the
            # warning message
            self.assertRaises(Snapshot.RestoreException, con.snapshot.restore,
                              ANY_GENERIC_ERROR, FORCE_ERROR_ONLINE)

            # simulates restore failure (might be because rollsync is running)
            con.filesystem.create(FILESYSTEM_FORCE_RESTORE_FAIL, '20M',
                                  'SFS_Pool')
            con.snapshot.create("snap-fail",
                              FILESYSTEM_FORCE_RESTORE_FAIL, "Int110-cache")
            err = None
            try:
                con.snapshot.restore("snap-fail",
                                     FILESYSTEM_FORCE_RESTORE_FAIL)
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, Snapshot.RestoreException))
            self.assertEquals(str(err), "File system failed to restore: SFS "
                "rollback ERROR V-288-2022 restore from rollback snap-fail "
                "failed.\nSFS rollback ERROR V-288-2236 Unable to restore "
                "file system FSRESTFAIL with rollback snap-fail.. "
                "Command: storage rollback restore FSRESTFAIL snap-fail")

            # simulates a restore while a rollsync action is running
            fs = con.filesystem.create('restore_not_running', '20M',
                                       'SFS_Pool')
            self.assertFalse(fs.is_restore_running())

            fs = con.filesystem.create(FILESYSTEM_RESTORE_STILL_RUNNING, '20M',
                                       'SFS_Pool')
            con.snapshot.create("rollback-running",
                              FILESYSTEM_RESTORE_STILL_RUNNING, "Int110-cache")
            self.assertTrue(fs.is_restore_running())
            err = None
            try:
                con.snapshot.restore("rollback-running",
                                     FILESYSTEM_RESTORE_STILL_RUNNING)
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, Snapshot.RollsyncRunning))
            self.assertEquals(str(err), "File system failed to restore: SFS "
                "rollback ERROR V-288-2022 restore from rollback "
                "rollback-running failed.\nSFS rollback ERROR V-288-2236 "
                "Unable to restore file system FSRESTRUN with rollback "
                "rollback-running.. Command: storage rollback restore "
                "FSRESTRUN rollback-running")

            err = None
            try:
                con.snapshot.delete("rollback-running",
                                     FILESYSTEM_RESTORE_STILL_RUNNING)
            except Exception, err:
                pass
            #self.assertTrue(isinstance(err, Snapshot.RollsyncRunning))

            # Test deleting snapshot
            del_snap = con.snapshot.create("Int110-storadm-del",
                                           "Int110-storadm", "Int110-cache")
            del_snap.delete()
            snapshots = con.snapshot.list()
            self.assertFalse(del_snap in snapshots)
            # Testing creation exceptions
            # Snapshot DoesNotExist exception
            self.assertRaises(Snapshot.DoesNotExist, con.snapshot.get,
                              "non_existient")

            # Snapshot creation AlreadyExist exception
            self.assertRaises(Snapshot.AlreadyExists, con.snapshot.create,
                              "Int110-storadm-snap", "Int110-storadm",
                              "Int110-cache")

            # Snapshot creation Filesystem.DoesNotExist exception
            self.assertRaises(FileSystem.DoesNotExist, con.snapshot.create,
                              "Int110-storadm-ombs", "non_existent",
                              "Int110-cache")

            # Snapshot creation Cache.DoesNotExist exception
            self.assertRaises(Cache.DoesNotExist, con.snapshot.create,
                              "Int110-storadm-ombs", "Int110-storadm",
                              "non_existent")

            # try to create a snapshot in case the cache is full
            con.cache.create("cache_full_test1", "20M", "SFS_Pool")
            cache = con.cache.get("cache_full_test1")
            self.assertTrue(bool(cache.available))
            con.ssh.mock_db.resources.cache.make_cache_full("cache_full_test1")
            cache = con.cache.get("cache_full_test1")
            self.assertFalse(bool(cache.available))

            err = ""
            try:
                con.snapshot.create("snap_cache_full_test1", "Int110-storadm",
                                    "cache_full_test1")
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, Snapshot.CreationException))
            self.assertEquals(str(err), 'Failed to create the snapshot '
                '"snap_cache_full_test1" for the file system "Int110-storadm" '
                'because the cache "cache_full_test1" is full. Snapshot '
                'creation failed: SFS rollback ERROR V-288-1883 fsck failed '
                'for snap_cache_full_test1. Command: storage rollback create '
                'space-optimized snap_cache_full_test1 Int110-storadm '
                'cache_full_test1')

            # any generic error
            self.assertRaises(Snapshot.CreationException, con.snapshot.create,
                              ANY_GENERIC_ERROR, "Int110-storadm",
                              "Int110-cache")

            # Testing deletion exceptions
            # Snapshot deletion Filesystem.DoesNotExist exception
            self.assertRaises(FileSystem.DoesNotExist, con.snapshot.delete,
                              "Int68-storadm_68-s", "non_existent")

            # Snapshot deletion Snapshot.DoesNotExist exception
            self.assertRaises(Snapshot.DoesNotExist, con.snapshot.delete,
                              "non_existent", "Int110-storadm")

            # Snapshot deletion any generic error
            self.assertRaises(Snapshot.DeletionException, con.snapshot.delete,
                              ANY_GENERIC_ERROR, "Int110-storadm")

            # Snapshot deletion when snapshot is online
            self.assertEquals(con.filesystem.get('Int110-storadm-snap').online,
                              False)
            con.filesystem.online('Int110-storadm-snap', True)
            self.assertEquals(con.filesystem.get('Int110-storadm-snap').online,
                              True)
            con.snapshot.delete("Int110-storadm-snap", "Int110-storadm")
            self.assertFalse(con.snapshot.exists("Int110-storadm-snap"))
            self.assertFalse(con.filesystem.exists("Int110-storadm-snap"))

            # Snapshot deletion error when snapshot is online, fail offline
            self.assertRaises(Snapshot.DeletionException, con.snapshot.delete,
                  FORCE_ERROR_OFFLINE, "Int110-storadm")

            # Snapshot deletion when snapshot is online and fs does not exist
            con.snapshot.create("Int110-storadm-snap", "Int110-storadm",
                                "Int110-cache")
            self.assertEquals(con.filesystem.get('Int110-storadm-snap').online,
                              False)
            con.execute('storage rollback online Int110-storadm-snap')
            self.assertEquals(con.filesystem.get('Int110-storadm-snap').online,
                              True)
            self.assertRaises(FileSystem.DoesNotExist, con.snapshot.delete,
                              "Int110-storadm-snap", "non_existent")

            err = ""
            try:
                con.filesystem.is_restore_running("non_existent")
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, FileSystem.DoesNotExist))

    def test_sfs(self):
        mock_args = "10.44.86.226", "support", "support"

        err = ''
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name,
                                   mock_connection_failure=True) as s:
                pass
        except Exception, err:
            pass

        self.assertTrue(isinstance(err, NasConnectionException))


        err = ''
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
                s.filesystem.create("some_other", '9999999T', 'SFS_Pool',
                                    layout="simple")
        except Exception, err:
            pass
        self.assertTrue(isinstance(err,
                                   FileSystem.InsufficientSpaceException))

        timeout_exc = NasExecutionTimeoutException("timeout")

        ssh_mock = SshClientMock(*mock_args)
        ssh_mock.mock_db = SfsMockDb()

        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.filesystem.create,
                          "sn", '10M', 'SFS_Pool', layout="simple")
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.share.create,
                          "/vx/sn", '1.2.3.4', 'ro')
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.filesystem.delete,
                          "rog1-test1G")
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.share.delete,
                          "/vx/ST51-fs1", '10.44.86.6')
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.cache.create,
                          "somecache", '10M', 'litp2')
        name = sfs.cache.list()[0].name
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.cache.delete,
                          name)
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.snapshot.create,
                          "my_snap", "my_filesystem", "my_cache")
        snap_name = sfs.snapshot.list()[0].name
        fs_name = sfs.filesystem.list()[0].name
        sfs = SfsMock(ssh_mock, exception=timeout_exc)
        self.assertRaises(NasExecutionTimeoutException, sfs.snapshot.delete,
                          snap_name, fs_name)

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            vx = VxCommands(s)
            s.ssh.run = mock.Mock(return_value=(1, 'out', 'this will fail'))
            self.assertRaises(VxCommandsException, vx.execute_cmd, 'command')
            s.ssh.run = mock.Mock(return_value=(0, 'out', ''))
            self.assertEqual('out', vx.execute_cmd('command'))

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            vx = VxCommands(s)
            all_data = vx.vxprint()
            fsd = vx.vxprint("Int56-cache")
            self.assertEquals(fsd, all_data["Int56-cache"])

            # the lines below are tests for the reported bug LITPCDS-9170
            # the fix was to separate the vxprint output, putting the "dc"
            # data in a separate dict, as it has the same keys as the volume
            # "vt" data. The fix is in "sfs.utils.VxPrintOutput.parse" method.
            fname = 'Int51-int51'
            self.assertTrue('dc' in all_data[fname])
            self.assertTrue(isinstance(all_data[fname]['dc'], dict))
            self.assertTrue(isinstance(all_data[fname]['sd'], list))
            fs = s.filesystem.get(fname)
            other = FileSystem(s, name=fname, size='20M',
                               layout='simple', pool='litp2')
            self.assertTrue(fs, other)

        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True) as s:
            self._test_sfs(s)
            self._test_sfs_size_comparison(s)

        # simulating intermittent connection issue when SFS gives an INFO
        # message instead of the expected output.
        output = (re.compile(r"storage\s+fs\s+list"),
                  "%s fs INFO V-288-2691 Found CVM master not in current "
                  "node, switching the console, current session will get "
                  "disconnected" % self.type, "")
        err = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, NasExecCommandException))
        self.assertTrue("%s output: %s fs INFO V-288-2691 Found CVM master not"
                        " in current node" % (self.driver_name.upper(),
                                              self.type) in str(err))

        # simulating exception on VxCommands
        output = (SfsMockDbFilesystem.regexes['vxprint'], "wrong_output", "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxprint -hrAF sd:'%type %name %assoc %kstate %len %column_pl_offset %state %tutil0 %putil0 %device'"), (0, 'wrong_output', ''))
            #self._test_sfs(s)


        vxp_out = """
TY NAME       KSTATE   LENGTH  PLOFFS  STATE  TUTIL0  PUTIL0
dg nbuapp     nbuapp     -        -        -        -      -       -


dm disk_1     disk_1     -        9755774656 -      -      -       -
dm disk_2     disk_2     -        76171777984 -     -      -       -
        """
        output = (SfsMockDbFilesystem.regexes['vxprint'], vxp_out, "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            vxprint_cmd = "vxprint -hrAF sd:'%type %name %assoc %kstate %len %column_pl_offset %state %tutil0 %putil0 %device'"
            self.assertEquals(s.ssh.run(vxprint_cmd), (0, vxp_out, ''))
            #self._test_sfs(s)
            fs_set = s.filesystem.list()
            self.assertEquals(fs_set[0].properties, {})
            self.assertEquals(fs_set[0].disk_alignment, 512)

        vxp_out = """
Disk group: sfsdg

TY NAME         ASSOC        KSTATE   LENGTH   PLOFFS   STATE    TUTIL0  PUTIL0
dg sfsdg        sfsdg        -        -        -        -        -       -

dm emc_clariion0_110 emc_clariion0_110 - 314506960 -    -        -       -
dm emc_clariion0_121 emc_clariion0_121 - 314506960 -    -        -       -

vt ossrc1-file_system4 -     ENABLED  -        -        ACTIVE   -       -
v  ossrc1-file_system4_tier1 ossrc1-file_system4 ENABLED 40960 - ACTIVE - -
pl ossrc1-file_system4_tier1-01 ossrc1-file_system4_tier1 ENABLED 40960 - ACTIVE - -
ssd sdb-02       ossrc1-file_system4_tier1-01 ENABLED 40960 0 -   -       -
dc ossrc1-file_system4_tier1_dco ossrc1-file_system4_tier1 - - - - -     -
v  ossrc1-file_system4_tier1_dcl gen ENABLED 544 -      ACTIVE   -       -
pl ossrc1-file_system4_tier1_dc-01 ossrc1-file_system4_tier1_dcl ENABLED 544 - ACTIVE - -
sd sdb-09       ossrc1-file_system4_tier1_dc-01 ENABLED 544 0 -  -       -
        """

        output = (SfsMockDbFilesystem.regexes['vxprint'], vxp_out, "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            vxprint_cmd = "vxprint -hrAF sd:'%type %name %assoc %kstate %len %column_pl_offset %state %tutil0 %putil0 %device'"
            self.assertEquals(s.ssh.run(vxprint_cmd), (0, vxp_out, ''))
            #self._test_sfs(s)
            fs = s.filesystem.get('ossrc1-file_system4')
            self.assertTrue(len(fs.properties) > 0)
            self.assertTrue('sd' not in fs.properties)
            self.assertTrue('ssd' in fs.properties)
            self.assertEquals(fs.disk_alignment, SfsSize.block_size)

        output = (SfsMockDbFilesystem.regexes['vxprint'], "", "some error")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            vxprint_cmd = "vxprint -hrAF sd:'%type %name %assoc %kstate %len %column_pl_offset %state %tutil0 %putil0 %device'"
            self.assertEquals(s.ssh.run(vxprint_cmd), (0, '', 'some error'))
            #self._test_sfs(s)
            fs_set = s.filesystem.list()
            self.assertEquals(fs_set[0].properties, {})

        output = (SfsMockDbFilesystem.regexes['vxdisk_list'], "wrong_output",
                  "")

        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdisk list d"), (0, 'wrong_output', ''))
            #self._test_sfs(s)


        output = (SfsMockDbFilesystem.regexes['vxdisk_list'], "", "some error")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdisk list d"), (0, '', 'some error'))
            #self._test_sfs(s)


        output = (SfsMockDbFilesystem.regexes['vxdisk_list'], "disk: name=some", "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdisk list d"),
                              (0, 'disk: name=some', ''))
            vx = VxCommands(s)
            self.assertRaises(VxCommandsException, vx.get_disk_group_id, 'foo')
            fs_set = s.filesystem.list()
            self.assertEquals(fs_set[0].disk_alignment, 512)


        output = (SfsMockDbFilesystem.regexes['vxdg'], "wrong_output", "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdg -q list d"), (0, 'wrong_output',''))
            #self._test_sfs(s)
            fs_set = s.filesystem.list()
            self.assertEquals(fs_set[0].disk_alignment, 512)


        output = (SfsMockDbFilesystem.regexes['vxdg'],
                  "alignment: 8192 (kilos)", "")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdg -q list d"), (0, output[1], ''))
            #self._test_sfs(s)
            fs_set = s.filesystem.list()
            self.assertEquals(fs_set[0].disk_alignment, 512)


        output = (SfsMockDbFilesystem.regexes['vxdg'], "", "some error")
        with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
            self.assertEquals(s.ssh.run("vxdg -q list d"), (0, '', 'some error'))
            #self._test_sfs(s)


        priv = SfsMock.check_privileges_cmd % ''
        output = (re.compile(priv), "Username: support\n", "")
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception, err:
            self.assertTrue(isinstance(err,
                                       NasBadPrivilegesException))


        priv = SfsMock.check_privileges_cmd % 'FORCE_FAIL'
        output = (re.compile(priv), "fail check privileges: fail", "")
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.sfs_user = 'FORCE_FAIL'
                s.filesystem.list()
        except Exception, err:
            self.assertTrue(isinstance(err,
                                       NasBadPrivilegesException))

        output = (re.compile(SfsMock.is_bash_cmd), "", "")
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception, err:

            self.assertTrue(isinstance(err,
                                       NasBadUserException))

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            s.filesystem.list()
            self.assertTrue(s.is_master)

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            s.filesystem.list()
            s.ssh._is_connected = False
            s.filesystem.list()
            self.assertFalse(s.ssh.is_connected())

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            s.ssh.mock_db.data['share']['list'] += '\nwrong line'
            err = ''
            try:
                s.share.list()
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, NasUnexpectedOutputException))
            cont = s.ssh.mock_db.data['share']['list'].replace('wrong line',
                                                               '')
            s.ssh.mock_db.data['share']['list'] = cont


        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            s.ssh.mock_db.resources.share.faulted_shares.append('\nwrong line')
            err = ''
            try:
                s.share.list()
            except Exception, err:
                pass
            self.assertTrue(isinstance(err, NasUnexpectedOutputException))
            s.ssh.mock_db.resources.share.faulted_shares.pop()

    def test_faulted_shares(self):
        faulted_shares = get_faulted_shares()

        mock_args = NasDrivers.Sfs, "10.44.86.226", "support", "support"
        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            shares = s.share.list()
            for share in shares:
                share_id = ShareResource.faulted_match_format % {
                                                        'client': share.client,
                                                        'name': share.name}
                if share_id in faulted_shares:
                    self.assertTrue(share.faulted)
                else:
                    self.assertFalse(share.faulted)

    def test_empty_pool_parsing(self):
        mock_args = "10.44.86.226", "support", "support"

        # testing empty pool issue
        fs_out = """
FS                        STATUS       SIZE    LAYOUT              MIRRORS   COLUMNS   USE%  NFS SHARED  CIFS SHARED  SECONDARY TIER  POOL LIST
========================= ======       ====    ======              =======   =======   ====  ==========  ===========  ==============  =========
A2345_6-789-fs1           online      3.00G    simple              -         -           3%     no          no           no           SFS_Pool
A2345_6789-fs1            online      3.00G    simple              -         -           3%     no          no           no
"""
        output = (re.compile(r"storage\s+fs\s+list"), fs_out, "")
        err = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.fs_get_max_number_of_attempts = 1
                s.filesystem.fs_get_delay_between_attemps = 1
                s.filesystem.get('A2345_6789-fs1')
        except NasException as err:
            pass
        self.assertTrue(isinstance(err, NasIncompleteParsedInformation))
        self.assertTrue(hasattr(err, 'parsed_data'))
        filesystem = err.parsed_data
        self.assertTrue(filesystem.pool is None)

    def test_invalid_pool_parsing(self):
        mock_args = "10.44.86.226", "support", "support"

        fs_out = """
FS                        STATUS       SIZE    LAYOUT              MIRRORS   COLUMNS   USE%  NFS SHARED  CIFS SHARED  SECONDARY TIER  POOL LIST
========================= ======       ====    ======              =======   =======   ====  ==========  ===========  ==============  =========
A2345_6-789-fs1           online      3.00G    simple              -         -           3%     no          no           no           SFS_Pool
A2345_6789-fs1            online      3.00G    simple              -         -           3%     no          no           no           An Invalid Pool
"""
        output = (re.compile(r"storage\s+fs\s+list"), fs_out, "")
        err = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception as err:
            pass

        self.assertTrue(isinstance(err, NasUnexpectedOutputException))

    def test_cache_parsing(self):
        mock_args = "10.44.86.226", "support", "support"

        output = (re.compile(r"storage\s+rollback\s+cache\s+list"), self.incomplete_cache_out, "")
        err = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.cache.list()
        except Exception as err:
            pass

        self.assertTrue(isinstance(err, NasIncompleteParsedInformation))


        err = None
        valid_cache = None
        invalid_cache = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                valid_cache = s.cache.get('105cache1')
                invalid_cache = s.cache.get('ST51-cache')
        except Exception as err:
            pass

        self.assertTrue(valid_cache is not None)
        self.assertTrue(invalid_cache is None)
        self.assertTrue(isinstance(err, NasIncompleteParsedInformation))
        self.assertTrue(isinstance(err.parsed_data, Cache))

    def test_fs_equal(self):
        mock_args = "10.44.86.226", "support", "support"

        with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
            fs_exist = s.filesystem.get('ossrc1-file_system4')
            fs_other = FileSystem(s, name='ossrc1-file_system4', size='10G',
                               layout='simple', pool='SFS_Pool')
            self.assertEqual(fs_exist, fs_other)

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket')
    @mock.patch('naslib.paramikopatch.HostKeyEntry')
    @mock.patch('naslib.paramikopatch.PatchedTransport._next_channel')
    @mock.patch('naslib.paramikopatch.PatchedTransport.start_client')
    @mock.patch('naslib.paramikopatch.PatchedTransport._send_user_message')
    @mock.patch('naslib.paramikopatch.PatchedTransport.accept')
    @mock.patch('naslib.paramikopatch.PatchedTransport.get_remote_server_key')
    @mock.patch('naslib.paramikopatch.Channel.exec_command')
    @mock.patch('naslib.paramikopatch.Channel.get_pty')
    @mock.patch('naslib.paramikopatch.Channel.recv_exit_status')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    def test_bad_host_key(self, _auth, recv_exit_status, get_pty, exec_command,
            get_remote_server_key, accept, _send_user_message, start_client,
            _next_channel, host_key_entry, _, getaddrinfo, connect):
        e = TypeError("Incorrect Padding")
        host_key_entry.from_line.side_effect = e
        exec_command.return_value = None
        get_pty.return_value = None
        recv_exit_status.return_value = 0
        original_missing_host_key = AutoAddPolicy.missing_host_key
        AutoAddPolicy.missing_host_key = mock.Mock(return_value=None)
        _next_channel.return_value = 1
        start_client.return_value = None
        _send_user_message.return_value = None
        accept.return_value = None
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='skey')
        get_remote_server_key.return_value = sk
        connect.return_value = True
        getaddrinfo.return_value = [['a', 1, 'b', 'c', 'd']]
        _auth.return_value = None
        client = SSHClient("somehost", "user", "password")
        client.connect()
        AutoAddPolicy.missing_host_key = original_missing_host_key

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket.settimeout')
    @mock.patch('naslib.paramikopatch.PatchedTransport._next_channel')
    @mock.patch('naslib.paramikopatch.PatchedTransport.start_client')
    @mock.patch('naslib.paramikopatch.PatchedTransport._send_user_message')
    @mock.patch('naslib.paramikopatch.PatchedTransport.accept')
    @mock.patch('naslib.paramikopatch.PatchedTransport.get_remote_server_key')
    @mock.patch('naslib.paramikopatch.Channel.exec_command')
    @mock.patch('naslib.paramikopatch.Channel.get_pty')
    @mock.patch('naslib.paramikopatch.Channel.recv_exit_status')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    def test_ssh_timeout(self, _auth, recv_exit_status, get_pty, exec_command,
            get_remote_server_key, accept, _send_user_message, start_client,
            _next_channel, settimeout, getaddrinfo, connect):
        exec_command.return_value = (None, None, None)
        get_pty.return_value = None
        recv_exit_status.return_value = 0
        _next_channel.return_value = 1
        start_client.return_value = None
        _send_user_message.return_value = None
        accept.return_value = None
        _auth.return_value = None
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='skey')
        get_remote_server_key.return_value = sk
        connect.return_value = True
        getaddrinfo.return_value = [['a', 1, 'b', 'c', 'd']]
        client = SSHClient("somehost", "user", "password")
        original_missing_host_key = AutoAddPolicy.missing_host_key
        AutoAddPolicy.missing_host_key = mock.Mock(return_value=None)
        with mock.patch('socket.socket') as soc:
            client.ssh._transport = PatchedTransport(soc)
        client.ssh._transport.active = True

        error_msg = 'A timeout of 0.5 seconds occurred after trying to ' \
                    'execute the following command remotely through SSH: ' \
                    '"ls". Error: Channel connection timed out.'
        err = ''
        try:
            client.run('ls', timeout=0.5)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, NasExecutionTimeoutException))
        self.assertEquals(str(err), error_msg)
        err = None
        try:
            client.ssh.exec_command("ls", timeout=0.5, get_pty=True)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, SSHException))

        client.ssh._transport.active = True
        try:
            client.ssh._transport.open_channel('forwarded-tcpip',
                                               ['1', 2], ['3', 4], timeout=0.1)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, SSHException))

        client.ssh._transport.active = True
        try:
            client.ssh._transport.open_channel('x11',
                                               ['1', 2], ['3', 4], timeout=0.1)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, SSHException))

        t = client.ssh._transport
        client.ssh._transport = None
        try:
            client.ssh.exec_command("ls", timeout=0.1, get_pty=True)
        except Exception as err:
            pass

        self.assertTrue(isinstance(err, SSHException))

        import threading
        with mock.patch.object(threading, 'Event') as Event:
            Event.isSet = mock.Mock(return_value=True)
            client.ssh._transport = t
            client.ssh._transport.active = True
            client.ssh.exec_command("ls", get_pty=True)

        client.ssh._transport.active = True
        ops = [False, True, True]
        def sumsg(*args, **kwargs):
            try:
                return ops.pop()
            except:
                return True
        del client._ssh._transport.active
        setattr(client._ssh._transport.__class__, 'active', property(sumsg))

        with mock.patch.object(threading._Event, 'isSet') as isSet:
            isSet.return_value = True
            getaddrinfo.return_value = [[1, 99, 'b', 'c', 'd']]
            err = None
            try:
                client.ssh.exec_command("ls", get_pty=True)
            except Exception as err:
                pass
            self.assertTrue(isinstance(err, SSHException))
            del client._ssh._transport.__class__.active
            setattr(client._ssh._transport, 'active', True)

        getaddrinfo.return_value = [[1, 1, 'b', 'c', 'd']]

        def ch(s, m=None):
            s._channels = {}

        original_send_user_message = PatchedTransport._send_user_message
        PatchedTransport._send_user_message = ch
        client._ssh.connect("somehost", 22, None, None)

        with mock.patch.object(threading, 'Event') as Event:
            Event.isSet = mock.Mock(return_value=True)
            client.ssh._transport.active = True
            err = None
            try:
                client.ssh.exec_command("ls", get_pty=True)
            except Exception as err:
                pass
            self.assertTrue(isinstance(err, SSHException))
        PatchedTransport._send_user_message = original_send_user_message

        client.ssh._transport = t
        client._ssh._log_channel = ""
        client._ssh._system_host_keys = {"somehost": {"skey": ["otherkey"]}}
        err = None
        try:
            client._ssh.connect("somehost", 22, None, None)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, PatchedBadHostKeyException))

        client._ssh._system_host_keys = {"somehost": {"skey": [sk]}}
        client._ssh.connect("somehost", 22, None, None, key_filename="")
        client._ssh.connect("somehost", 22, None, None, key_filename=[])
        settimeout.side_effect = Exception("any")
        err = None
        try:
            client._ssh.connect("somehost", 22, None, None, key_filename=[],
                                timeout=999)
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, Exception))
        self.assertEquals(str(err), 'any')
        AutoAddPolicy.missing_host_key = original_missing_host_key

    @mock.patch('naslib.paramikopatch.SSHClient.exec_command')
    @mock.patch('naslib.ssh.SSHClient.connect')
    def test_run_timeout_exception(self, connect, exec_command):
        import socket
        exec_command.side_effect = socket.timeout
        connect.return_value = None
        client = SSHClient('somehost', 'user', 'password')
        client._ssh = ParamikoSSHClient()
        err = None
        try:
            client.run('ls')
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, NasExecutionTimeoutException))

    # def test_nas_drivers(self):
    #     self.assertRaises(NasDriverDoesNotExist, NasDrivers.get_driver,
    #                       'invalid_driver')
    #     self.assertRaises(NasDriverDoesNotExist, NasDrivers.get_mock,
    #                       'invalid_mock')

    def test_mock_use(self):
        mock_args = NasDrivers.Sfs, "10.44.86.226", "support", "support"
        output = ""
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception, err:
            self.assertTrue(isinstance(err, MockException))
        output = ("", "")
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.list()
        except Exception, err:
            self.assertTrue(isinstance(err, MockException))
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name) as s:
                s.execute('wrong_command')
        except Exception, err:
            self.assertTrue(isinstance(err, MockException))
        try:
            SshClientMock("host", "user", "password")
        except Exception, err:
            self.assertTrue(isinstance(err, MockException))

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket')
    @mock.patch('naslib.paramikopatch.PatchedTransport._next_channel')
    @mock.patch('naslib.paramikopatch.PatchedTransport.start_client')
    @mock.patch('naslib.paramikopatch.PatchedTransport._send_user_message')
    @mock.patch('naslib.paramikopatch.PatchedTransport.accept')
    @mock.patch('naslib.paramikopatch.PatchedTransport.open_session')
    @mock.patch('naslib.paramikopatch.PatchedTransport.close')
    @mock.patch('naslib.paramikopatch.PatchedTransport.get_remote_server_key')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    @mock.patch('naslib.paramikopatch.Channel')
    @mock.patch('naslib.paramikopatch.AutoAddPolicy.missing_host_key')
    def test_ssh_commands(self, missing_host_key, ch, _auth,
            get_remote_server_key, close, open_session, accept,
            _send_user_message, start_client, _next_channel, socket,
            getaddrinfo, connect):
        ch.get_pty.return_value = None
        _next_channel.return_value = 1
        start_client.return_value = None
        _send_user_message.return_value = None
        accept.return_value = None
        mock_chan = mock.Mock()
        mock_chan.settimeout.return_value = None
        mock_chan.exec_command.return_value = None
        mock_chan.recv_exit_status.side_effect = [0, 1]
        result = StringIO('result')
        err = StringIO('err')
        empty = StringIO('')
        result.channel = mock_chan
        err.channel = mock_chan
        empty.channel = mock_chan
        mock_chan.makefile.side_effect = [empty, result, empty, empty]
        mock_chan.makefile_stderr.side_effect = [empty, err]
        open_session.return_value = mock_chan
        close.return_value = None
        sk = mock.Mock()
        sk.get_fingerprint.return_value = 'skey'
        sk.get_name.return_value = 'rsa'
        get_remote_server_key.return_value = sk
        connect.return_value = True
        getaddrinfo.return_value = [('a', 1, 'b', 'c', 'd')]
        _auth.return_value = None
        client = SSHClient('somehost', 'user', 'password')
        missing_host_key.return_value = None
        client.ssh._transport = PatchedTransport(socket)
        client.ssh._transport.active = True
        _, out, err = client.run('ls')
        self.assertEquals(out, 'result')
        self.assertEquals(err, '')
        _, out, err = client.run('lsssss')
        self.assertEquals(out, '')
        self.assertEquals(err, 'err')
        client.close()

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket')
    @mock.patch('naslib.paramikopatch.HostKeyEntry')
    @mock.patch('naslib.paramikopatch.PatchedTransport._next_channel')
    @mock.patch('naslib.paramikopatch.PatchedTransport.start_client')
    @mock.patch('naslib.paramikopatch.PatchedTransport._send_user_message')
    @mock.patch('naslib.paramikopatch.PatchedTransport.accept')
    @mock.patch('naslib.paramikopatch.PatchedTransport.get_remote_server_key')
    @mock.patch('naslib.paramikopatch.Channel.exec_command')
    @mock.patch('naslib.paramikopatch.Channel.get_pty')
    @mock.patch('naslib.paramikopatch.Channel.recv_exit_status')

    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    def test_get_remote_host_key(self, _auth, recv_exit_status, get_pty, exec_command, get_remote_server_key, accept,
            _send_user_message, start_client, _next_channel, host_key_entry,
            socket, getaddrinfo, connect):
        e = TypeError("Incorrect Padding")
        host_key_entry.from_line.side_effect = e
        exec_command.return_value = None
        get_pty.return_value = None
        recv_exit_status.return_value = 0
        _next_channel.return_value = 1
        start_client.return_value = None
        _send_user_message.return_value = None
        accept.return_value = None
        _auth.return_value = None
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='rsa')
        get_remote_server_key.return_value = sk
        socket.return_value = socket
        connect.return_value = True
        getaddrinfo.return_value = [('a', 1, 'b', 'c', 'd')]
        key = SSHClient.get_remote_host_key('somehost')
        self.assertEquals(key.get_fingerprint(), 'skey')
        self.assertEquals(key.get_name(), 'rsa')

        # test sock_stream_info is None case, SSHException
        getaddrinfo.return_value = []
        err = None
        try:
            SSHClient.get_remote_host_key('somehost')
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, SSHException))
        self.assertEquals('No suitable address family for somehost', str(err))

        # test sock.settimeout Exception
        getaddrinfo.return_value = [('a', 1, 'b', 'c', 'd')]
        socket.settimeout.side_effect = Exception('some exception')
        err = None
        try:
            SSHClient.get_remote_host_key('somehost')
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, Exception))

    @mock.patch('__builtin__.open')
    def test_save_host_key(self, mock_open):
        known_hosts_content = """
|1|lds10xNOFyAM7rfTL/baaGiomU0=|lmWTJueScnH7qnKSwHxc+jBOd6g= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GAAA=
|1|/AG1tHlDWDBgwx6wn5F7DxPZ6R8=|6+LV53KMH2lfNkqpQ/Cbvi3xtAU= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC86anZpnhX37u8uOKSSM6LN64wBA6N3gWw4ahMQ5YvR0GOTFqbIBzKcw8CbgwIXiHvS0yAI0t7tJiUwE6XjxSzt73NwdIrjywrhqq9vFnlKWkznZQgktfAmyWlp4sYYTpAaiw9NJxvd1I9wN2zW7Bfl7gwz5Lo5EFd/ekhqjgzcQ==
|1|WFmKaJTsu4VvmwDkLWLVHPqI/SI=|3Kr41xUwOQJS88BJHyuXjNf1ODA= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC86anZpnhX37u8uOKSSM6LN64wBA6N3gWw4ahMQ5YvR0GOTFqbIBzKcw8CbgwIXiHvS0yAI0t7tJiUwE6XjxSzt73NwdIrjywrhqq9vFnlKWkznZQgktfAmyWlp4sYYTpAaiw9NJxvd1I9wN2zW7Bfl7gwz5Lo5EFd/ekhqjgzcQ==
|1|e3CbwSjhk0dg+k5rx/HM1uKJZtE=|R6oOg9tgxMHjqTJk5qwPsw339AQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAnGOVllla+nZ8C2GJ8dlMNs6zh/5uD1++8G85nJLRIYzRTVxMLivrI6qdH7+/khAdbK6oItwiZXhIB7upzcM6anST30xB8HEgXnlIg4U7UT5Ej1uLCzNPZPICaHrFKCAhD07uIonT0OOw8IbK4zRHUyXH8I6WLVjheSdn9qnB6dC80fQdXptxlXl6af7Gp956/u3mPIg6l421sw1rnoH7Na+FE0H/m/r0i2HbNA1VAYYZRGVu3lrrsy/YLaxRnDwzGqSXEeAKIRLRQZOQmct1cYAofAFqfOLGgPfZBoNJ6dPLNHaxHgeiybuTpTps0NR+8BnhH3UODJDNT6xMz1/kIw==
|1|ckGZWo9Zn2/d9GCVmZBBk5VGUw0=|gRidOGAhEZjxCZJLNABBZM/UTTU= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAnGOVllla+nZ8C2GJ8dlMNs6zh/5uD1++8G85nJLRIYzRTVxMLivrI6qdH7+/khAdbK6oItwiZXhIB7upzcM6anST30xB8HEgXnlIg4U7UT5Ej1uLCzNPZPICaHrFKCAhD07uIonT0OOw8IbK4zRHUyXH8I6WLVjheSdn9qnB6dC80fQdXptxlXl6af7Gp956/u3mPIg6l421sw1rnoH7Na+FE0H/m/r0i2HbNA1VAYYZRGVu3lrrsy/YLaxRnDwzGqSXEeAKIRLRQZOQmct1cYAofAFqfOLGgPfZBoNJ6dPLNHaxHgeiybuTpTps0NR+8BnhH3UODJDNT6xMz1/kIw==
|1|r8orEdNW7mAwAnC7GzVbIn0+h4k=|MDt8IEKO2uHIARnvUh65UO5u874= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC86anZpnhX37u8uOKSSM6LN64wBA6N3gWw4ahMQ5YvR0GOTFqbIBzKcw8CbgwIXiHvS0yAI0t7tJiUwE6XjxSzt73NwdIrjywrhqq9vFnlKWkznZQgktfAmyWlp4sYYTpAaiw9NJxvd1I9wN2zW7Bfl7gwz5Lo5EFd/ekhqjgzcQ==
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        to_save_file = StringIO()
        mock_open.side_effect = [StringIO(known_hosts_content), to_save_file]
        new_host_key = 'AAAAB3NzaC1yc2EAAAABIwAAAQEAxhxZ5guBT1Q0J67KuOg7f276' \
                       'S/sj0aoLZUXE/U3x/usT5/2abJA20bmLYQAL+wcAZr0YlQ9YhQUW' \
                       'zmQ3IQOmCKuKFZBz9U+zhmq1yWOSVa5LS4pnXvukVNq/J1tgu2Ox' \
                       'Wkm59ZOKXDJ0qQgWQHLS/DlVxJJ2k7wShp8VkQkmivA3icMEAJyN' \
                       '5W/H5DOsTBNRjG0sXFG6GeUoiErs/yVE2149Ytd+7cBSFmaKN6Ct' \
                       'dlEozWgSMKuLMM9Fhq2jPmF3bS2dOhIKMYf0ymifRnAe3z7Ux8Rz' \
                       '9A3OhYJMifywCr0i/NxjJ1pr1JdMquIO2VjxGcZSSSNB+gjrMRiF' \
                       '0Ongdw=='
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='ssh-rsa')
        sk.get_base64 = mock.Mock(return_value=new_host_key)
        SSHClient.save_host_key('somehost', sk)
        self.assertEquals('somehost ssh-rsa %s' % new_host_key,
                          to_save_file.buflist[-1].strip())

    @mock.patch('__builtin__.open')
    @mock.patch('os.path.exists')
    @mock.patch('os.makedirs')
    def test_save_host_key_no_known_hosts_file(self, mkd, exists, mock_open):
        import os
        to_save_file = StringIO()
        exists.return_value = False
        mkd.return_value = None
        io_error = IOError()
        io_error.errno = os.errno.ENOENT
        mock_open.side_effect = [io_error, to_save_file]
        new_host_key = 'AAAAB3NzaC1yc2EAAAABIwAAAQEAxhxZ5guBT1Q0J67KuOg7f276' \
                       'S/sj0aoLZUXE/U3x/usT5/2abJA20bmLYQAL+wcAZr0YlQ9YhQUW' \
                       'zmQ3IQOmCKuKFZBz9U+zhmq1yWOSVa5LS4pnXvukVNq/J1tgu2Ox' \
                       'Wkm59ZOKXDJ0qQgWQHLS/DlVxJJ2k7wShp8VkQkmivA3icMEAJyN' \
                       '5W/H5DOsTBNRjG0sXFG6GeUoiErs/yVE2149Ytd+7cBSFmaKN6Ct' \
                       'dlEozWgSMKuLMM9Fhq2jPmF3bS2dOhIKMYf0ymifRnAe3z7Ux8Rz' \
                       '9A3OhYJMifywCr0i/NxjJ1pr1JdMquIO2VjxGcZSSSNB+gjrMRiF' \
                       '0Ongdw=='
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='ssh-rsa')
        sk.get_base64 = mock.Mock(return_value=new_host_key)
        SSHClient.save_host_key('somehost', sk)
        self.assertEquals('somehost ssh-rsa %s' % new_host_key,
                          to_save_file.buflist[-1].strip())

    @mock.patch('__builtin__.open')
    @mock.patch('os.path.exists')
    @mock.patch('os.makedirs')
    def test_save_host_key_no_known_hosts_file_any_errno(self, mkd, exists, mock_open):
        import os
        to_save_file = StringIO()
        exists.return_value = False
        mkd.return_value = None
        io_error = IOError()
        io_error.errno = 9999999999
        mock_open.side_effect = [io_error, to_save_file]
        new_host_key = 'AAAAB3NzaC1yc2EAAAABIwAAAQEAxhxZ5guBT1Q0J67KuOg7f276' \
                       'S/sj0aoLZUXE/U3x/usT5/2abJA20bmLYQAL+wcAZr0YlQ9YhQUW' \
                       'zmQ3IQOmCKuKFZBz9U+zhmq1yWOSVa5LS4pnXvukVNq/J1tgu2Ox' \
                       'Wkm59ZOKXDJ0qQgWQHLS/DlVxJJ2k7wShp8VkQkmivA3icMEAJyN' \
                       '5W/H5DOsTBNRjG0sXFG6GeUoiErs/yVE2149Ytd+7cBSFmaKN6Ct' \
                       'dlEozWgSMKuLMM9Fhq2jPmF3bS2dOhIKMYf0ymifRnAe3z7Ux8Rz' \
                       '9A3OhYJMifywCr0i/NxjJ1pr1JdMquIO2VjxGcZSSSNB+gjrMRiF' \
                       '0Ongdw=='
        sk = mock.Mock()
        sk.get_fingerprint = mock.Mock(return_value='skey')
        sk.get_name = mock.Mock(return_value='ssh-rsa')
        sk.get_base64 = mock.Mock(return_value=new_host_key)
        SSHClient.save_host_key('somehost', sk)
        self.assertEquals('somehost ssh-rsa %s' % new_host_key,
                          to_save_file.buflist[-1].strip())


    def test_patched_host_keys_lookup(self):
        known_hosts_content = """
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        mock_open = mock.Mock(return_value = StringIO(known_hosts_content))
        with mock.patch('__builtin__.open', mock_open) as m:
            host_keys = PatchedHostKeys('known_hosts')
        data = host_keys.lookup('1.1.1.1')
        self.assertEquals(data.keys(), ['ssh-rsa'])
        self.assertEquals(len(data['ssh-rsa']), 2)
        self.assertEquals(data['ssh-rsa'][0].get_name(), 'ssh-rsa')
        self.assertEquals(data['ssh-rsa'][1].get_name(), 'ssh-rsa')

        # the action set below shouldn't do anything
        data['ssh-rsa'] = []
        self.assertEquals(data.keys(), ['ssh-rsa'])
        self.assertEquals(len(data['ssh-rsa']), 2)

        # setting a key with the base64 key already in the file
        string_key = "AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ=="
        data['ssh-rsa'] = [RSAKey(data=base64.decodestring(string_key))]
        self.assertEquals(data.keys(), ['ssh-rsa'])
        self.assertEquals(len(data['ssh-rsa']), 2)

        # setting a key with the base64 key not in the file
        string_key = "AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GAAA="
        data['ssh-rsa'] = [RSAKey(data=base64.decodestring(string_key))]
        self.assertEquals(data.keys(), ['ssh-rsa'])
        self.assertEquals(len(data['ssh-rsa']), 3)

        with self.assertRaises(KeyError) as context:
            data['wrong-key']

        with self.assertRaises(KeyError) as context:
            del data['wrong-key']

        del data['ssh-rsa']
        with self.assertRaises(KeyError) as context:
            del data['ssh-rsa']

    def test_patched_host_keys(self):
        known_hosts_content = """
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        mock_open = mock.Mock(return_value = StringIO(known_hosts_content))
        with mock.patch('__builtin__.open', mock_open) as m:
            host_keys = PatchedHostKeys('known_hosts')
        self.assertEquals(len(host_keys.keys()), 4)
        self.assertTrue('1.1.1.1' in host_keys.keys())
        self.assertEquals(host_keys['1.1.1.1'].keys(), ['ssh-rsa'])
        self.assertEquals(len(host_keys['1.1.1.1']['ssh-rsa']), 2)  # 2 different keys for the same host

        different_key = RSAKey(data=base64.decodestring("AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GAAA="))
        host_keys.add('1.1.1.1', 'ssh-rsa', different_key)
        self.assertEquals(len(host_keys.keys()), 4)  # keep the same amount of hostnames
        self.assertTrue('1.1.1.1' in host_keys.keys())
        self.assertEquals(host_keys['1.1.1.1'].keys(), ['ssh-rsa'])
        self.assertEquals(len(host_keys['1.1.1.1']['ssh-rsa']), 3)  # 3 different keys for the same host now though

        same_key = RSAKey(data=base64.decodestring("AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ=="))
        host_keys.add('1.1.1.1', 'ssh-rsa', same_key)
        self.assertEquals(len(host_keys.keys()), 4)  # keep the same amount of hostnames
        self.assertTrue('1.1.1.1' in host_keys.keys())
        self.assertEquals(host_keys['1.1.1.1'].keys(), ['ssh-rsa'])
        self.assertEquals(len(host_keys['1.1.1.1']['ssh-rsa']), 3)  # now till 3 different keys for the same host as the base64 key is *exactly* the same

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket')
    @mock.patch('threading._Event.is_set')
    @mock.patch('threading._Event.isSet')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    @mock.patch('__builtin__.open')
    def test_connect_unknown_host(self, mock_open, _auth, isSet, is_set, _, getaddrinfo, connect):
        getaddrinfo.return_value = [('a', 1, 'b', 'c', 'd')]
        connect.return_value = True
        def fake_start(self):
            self.active = True
            self.initial_kex_done = True
            self.host_key = RSAKey(data=base64.decodestring("AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GAAA="))
        original_start = PatchedTransport.start
        PatchedTransport.start = fake_start
        isSet.return_value = True
        _auth.return_value = None
        known_hosts_content = """
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        is_set.side_effect = [False, True]
        mock_open.side_effect = [StringIO(known_hosts_content), StringIO()]
        ssh = SSHClient('unknown-host', 'user', 'password')
        err = None
        try:
            ssh.connect()
        except Exception as err:
            pass
        self.assertEqual(err, None)
        PatchedTransport.start = original_start

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('socket.socket')
    @mock.patch('threading._Event.is_set')
    @mock.patch('threading._Event.isSet')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    @mock.patch('StringIO.StringIO.close')
    @mock.patch('__builtin__.open')
    def test_copy_key_and_connect_success(self, mock_open, sio_close, _auth, isSet, is_set, _, getaddrinfo, connect):
        getaddrinfo.return_value = [('a', 1, 'b', 'c', 'd')]
        connect.return_value = True
        server_key = RSAKey(data=base64.decodestring("AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GAAA="))
        original_start = PatchedTransport.start
        def fake_start(self):
            self.active = True
            self.initial_kex_done = True
            self.host_key = server_key
        PatchedTransport.start = fake_start

        isSet.return_value = True
        is_set.side_effect = [False, True, False, True, False, True, False, True, False, True, False, True]

        _auth.return_value = None
        sio_close.return_value = None
        known_hosts_content = """
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
2.2.2.2 ssh-rsa CORRUPTED_ONE_eqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        file_reference = StringIO(known_hosts_content)
        def mo(filename, mode):
            file_reference.pos = 0
            file_reference.seek(0)
            return file_reference
        mock_open.side_effect = mo

        original_close = PatchedTransport.close
        PatchedTransport.close = mock.Mock(return_value=None)

        remote_key = SSHClient.get_remote_host_key('host')
        self.assertEquals(remote_key, server_key)

        ssh = SSHClient('host', 'user', 'password')

        # test first without saving the key
        err = None
        try:
            ssh.connect()
        except Exception as err:
            pass
        self.assertEqual(err, None)

        # now testing after saving

        SSHClient.save_host_key('host', remote_key)
        ssh.connect()
        ssh.close()

        # different host key for the same host now (simulate  SFS failover situation)
        other_server_key = RSAKey(data=base64.decodestring("AAAAB3NzaC1yc2EAAAADAQABAAAAgQC86anZpnhX37u8uOKSSM6LN64wBA6N3gWw4ahMQ5YvR0GOTFqbIBzKcw8CbgwIXiHvS0yAI0t7tJiUwE6XjxSzt73NwdIrjywrhqq9vFnlKWkznZQgktfAmyWlp4sYYTpAaiw9NJxvd1I9wN2zW7Bfl7gwz5Lo5EFd/ekhqjgzcQ=="))
        def fake_start(self):
            self.active = True
            self.initial_kex_done = True
            self.host_key = other_server_key
        PatchedTransport.start = fake_start

        new_remote_key = SSHClient.get_remote_host_key('host')
        self.assertEquals(new_remote_key, other_server_key)

        # test first without saving the key
        err = None
        try:
            ssh.connect()
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, SSHException))
        self.assertEquals(str(err), 'Host key for server host does not match!')
        ssh.close()

        # now testing after saving
        new_remote_key = SSHClient.get_remote_host_key('host')
        self.assertEquals(new_remote_key, other_server_key)
        SSHClient.save_host_key('host', new_remote_key)
        ssh.connect()
        ssh.close()

        PatchedTransport.start = original_start
        PatchedTransport.close = original_close

    @mock.patch('socket.socket.connect')
    @mock.patch('socket.getaddrinfo')
    @mock.patch('naslib.paramikopatch.SSHClient._auth')
    def test_get_remote_host_key_timeout(self, _auth, getaddrinfo, connect):
        getaddrinfo.return_value = [(1, 1, 'b', 'c', 'd')]
        _auth.return_value = None
        from socket import timeout
        connect.side_effect = timeout
        err = None
        try:
            SSHClient.get_remote_host_key('host')
        except Exception as err:
            pass
        self.assertTrue(isinstance(err, NasException))

    @mock.patch('__builtin__.open')
    def test_get_known_hosts_keys(self, mock_open):
        known_hosts_content = """
|1|nO527Fp0g6b2u8t62Y3CVaAvACo=|nUhi0mGYskcWpMd7xp1p0PlaFYM= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAz4Mx3d1Houmq12jr0Pwqh84YfnPRvCHJ02WeTuiBjfZgRogj/EYhfbwCvW0m8L4/TUm4WhwPOn+8pbxnNadoB1E4Xy6En9FNDx8XZGlJNkmbIqvFzGXFLRGEQqTAY0BWOrbnP/hoo9e9dpxOrtHSAzdYEwMY4I8g1NMWQoPU9v1UT3m4jYfTzp0lMH5I8U7+sQxLsUdWfoAteiyc2ldzJLxnsFNRjpCjLYxuX757bJkeub3KAy09KZwIddpdxdpcgW09v+MCzoTxLiqrt7ojeSjz/yba0PTD9LM2OemPHZmr0CkZZ52D5JrJjbfCl0+NYtM5ONEaCPao4FaBcxto8Q==
|1|SYGH0OHF0EsQJZHgt15iUBpFsAk=|rlps+sOFWJFAZ/Y2X5xSzrLtnkQ= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
|1|DwHb26gFhNfZ5MStJ3nGlIsmpgY=|wFKBFMNPnuR1qImxWkUZ7T7qvXg= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
2.2.2.2 ssh-rsa CORRUPTED_ONE_oHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=
1.1.1.1 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==
"""
        mock_open.return_value = StringIO(known_hosts_content)
        keys = SSHClient.get_known_hosts_keys().get('non-existent-host')
        self.assertTrue(keys is None)

        mock_open.return_value = StringIO(known_hosts_content)
        keys = SSHClient.get_known_hosts_keys().get('1.1.1.1')
        self.assertFalse(keys is None)
        self.assertEquals(keys.keys(), ['ssh-rsa'])
        self.assertEquals(len(keys['ssh-rsa']), 2)
        self.assertEquals(keys['ssh-rsa'][0].get_name(), 'ssh-rsa')
        self.assertEquals(keys['ssh-rsa'][1].get_name(), 'ssh-rsa')
        self.assertEquals(keys['ssh-rsa'][0].get_base64(), 'AAAAB3NzaC1yc2EAAAABIwAAAIEA1tpsh/tUchGaleEmTcEIQuxXxzOyq6uMQgN0QsbTmRNzgtKCbBitwqPO3sxMVWyIpF9DpK2/VFDxdJAE/tHB7Tn/2ogrKAGtn4WXWtUH8YuDitVGUhpfrZGpvaqD7QciCaYdHs7kBAMgkD8IY8q/8SCrnNEAaMp+rSoy+97GeZ8=')
        self.assertEquals(keys['ssh-rsa'][1].get_base64(), 'AAAAB3NzaC1yc2EAAAABIwAAAQEAyb/XrK6W3ZjLKafS3HFILL8+Hi+aoHxnqNhHzHWF4TZaVRKSZRLCWybjMNpopJOLWs/QC5JBeqERg88ZSqnemLo8dZaa/x52ohomFlyPRCe2JfyJPl4mki8CFfBHoCvXEDEliLmVnkaTGVTxwnNA0eMsIvJkxGpnPQ3qxakajlXFn0toykXFmv1STY96CwaayrqOCctjXptn3kc9UgBoOJlQhpEgHRoixl64dxgX2+SA2n6o4Xt9qDZH/g2/VDrlMU42jfDPTdWBwcJagWx6AZBTDdr5uraXkzVl5wtb2u3jZf8rdpMl7IVJaMYwz7XDj7wOdWXGduBhU/pB2c4CUQ==')

    @mock.patch(
        'naslib.nasmock.ssh.SshClientMock.get_resource_action_kwargs_by_command')
    @mock.patch(
        'naslib.nasmock.ssh.SshClientMock.run')
    def test_driver_discovery(self, run, get_resource_action_kwargs_by_command):
        mock_args = "10.44.86.226", "support", "support"
        get_resource_action_kwargs_by_command.return_value = 0, '', ''
        run.return_value = 0, '', ''
        ssh_mock = SshClientMock(*mock_args)
        ssh_mock.mock_db = SfsMockDb()
        sfs = SfsMock(ssh_mock)
        try:
            disc = sfs.verify_discovery()
        except MockException as err:
            pass
        self.assertEqual(disc, True)

        run.return_value = 1, '', ''
        try:
            disc = sfs.verify_discovery()
        except Exception as err:
            pass
        self.assertEqual(disc, False)

    def test_build_shares_list(self):
        lines = [
                '/vx/testfs 1.1.1.1/12 (rw,nordirplus) ',
                '/vx/testfs * (rw,nordirplus) '
                ]
        faulted_lines = []
        mock_share = ShareResource("nas")
        output = mock_share._build_shares_list(lines, faulted_lines)
        self.assertEquals(output[0].name, '/vx/testfs')
        self.assertEquals(output[0].client, '1.1.1.1/12')
        self.assertEquals(output[1].name, '/vx/testfs')
        self.assertEquals(output[1].client, '')

    def test_execute_error(self):
        mock_args = "10.44.86.226", "support", "support"
        ssh_mock = SshClientMock(*mock_args)
        sfs = SfsMock(ssh_mock)
        sfs._run = mock.MagicMock(return_value=(0, 'out', 'this will fail'))
        self.assertRaises(NasExecCommandException, sfs.execute, 'command')
        # this will succeed - first entry in STDERRS_TO_IGNORE
        sfs._run = mock.MagicMock(return_value=
                                  (0, 'out', 'Waiting for other command (nfs '
        'share add rw,nordirplus /vx/mytestfs0 172.1.1.1/12) to complete'))
        self.assertEqual(['out'], sfs.execute('command'))
        # this will succeed - second entry in STDERRS_TO_IGNORE
        sfs._run = mock.MagicMock(return_value=(0, 'out', '...'))
        self.assertEqual(['out'], sfs.execute('command'))
        # this will succeed - third entry in STDERRS_TO_IGNORE
        sfs._run = mock.MagicMock(return_value=
                                  (0, 'out', 'cat: /opt/VRTSnas/log/vxvmtag.lock.lock: '
        'No such file or directory'))
        self.assertEqual(['out'], sfs.execute('command'))
