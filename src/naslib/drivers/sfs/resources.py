##############################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,W0221,E1101
""" This module contains the abstraction implementation for Symantec FileStore
as the resources for the Sfs class based on the following base resources:
 - NasShareBase;
 - NasFileSystemBase;
 - NasDiskBase;
 - NasPoolBase;
 - NasCacheBase;
 - NasSnapshotBase.

Each one of the resources classes in this module repectively based on the
NasResourceBase mentioned above has the real implementation of the following
base methods:
 - list;
 - create;
 - delete.
"""

import re
import time

from ...nasexceptions import NasException, NasExecCommandException, \
    NasExecutionTimeoutException, NasUnexpectedOutputException, \
    NasIncompleteParsedInformation
from ...baseresources import FileSystemResourceBase, PoolResourceBase, \
                             ShareResourceBase, DiskResourceBase, \
                             CacheResourceBase, SnapshotResourceBase
from ...objects import Pool, FileSystem, Share, Cache, Snapshot
from ...resourceprops import UnitsSize, Size
from .objects import SfsFileSystem, SfsCache, SfsSnapshot
from .parsers import VxPropertiesSimpleOutputParser
from .resourceprops import SfsSize
from .utils import VxCommands, VxCommandsException


# these constants below are to define the timeout in minutes for running
# commands via SSH using paramiko.
MINUTE = 60  # seconds
LISTING_TIMEOUT = 5 * MINUTE
CREATION_TIMEOUT = 15 * MINUTE
DELETION_TIMEOUT = 15 * MINUTE
ON_OFF_LINE_TIMEOUT = 5 * MINUTE


class ShareResource(ShareResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    share resource.
    """
    display_regex = re.compile(r"^(?P<name>[/\w:-]+)\s+(?P<client>[\w\.\*/]+)"
                               r"\s+\((?P<options>[\w,]+)\)$")
    faulted_shares_regex = re.compile(r"^(?P<name>[/\w:-]+)\s+"
                                  r"(?P<client>[\w\.\*/]+)\s*:\s*[\w\.-]+\s*$")
    faulted_delimiter = "Faulted Shares:"
    faulted_match_format = "%(name) s%(client)s"

    def _build_shares_list(self, lines, faulted_shares_lines):
        """ Helper to build a list of Shares objects based on the
        defined "display_regex" as a regular expression for each line of
        the output of NFS and also checks the Faulted Shares.
        """
        faulted = []
        for line in faulted_shares_lines:
            if not line.strip():
                continue
            match = self.faulted_shares_regex.match(line)
            if not match:
                raise NasUnexpectedOutputException('It\'s not possible to '
                    'parse the output of faulted shares received from %s. '
                    'Line output: "%s".' % (str(self.nas), line))
            faulted.append(self.faulted_match_format % match.groupdict())

        obj_list = []
        for line in [i.strip() for i in lines if i]:
            data = self.parse_displayed_line(line)
            data['faulted'] = (self.faulted_match_format % data) in faulted
            if data['client'] == "*":
                data['client'] = ""
            obj_list.append(self._build_nas_object(**data))
        return obj_list

    def list(self):
        """ Returns a list of Share resources items retrieved by SFS server.
        """
        lines = self.nas.execute("nfs share show", timeout=LISTING_TIMEOUT)
        faulted_shares_lines = []
        shares_and_faulted = '\n'.join(lines).split(self.faulted_delimiter)
        if len(shares_and_faulted) == 2:
            shares, faulted_shares = shares_and_faulted
            lines = shares.splitlines()
            faulted_shares_lines = faulted_shares.splitlines()
        return self._build_shares_list(lines, faulted_shares_lines)

    def create(self, path, client, options):
        """ Creates a share with a given path, clients and options. Options
        must be a list of strings. A share is unique identified by its path
        AND its client. In case of failures it raises a NasCreationException.
        """
        ops = ','.join(options) if hasattr(options, '__iter__') else options
        cmd = "nfs share add %s %s %s" % (ops, path, client)
        try:
            self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "Share creation failed: %s. Command: %s" % (str(err), cmd)
            raise Share.CreationException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the share was created or not
            if not self.exists(path, client):
                raise err
        return self._build_nas_object(name=path, client=client,
                                      options=ops)

    def delete(self, path, client):
        """ Deletes a Sfs Share given a path and client. A share is unique
        identified by its path AND its client. In case of failures it raises a
        NasDeletionException.
        """
        cmd = "nfs share delete %s %s" % (path, client)
        try:
            self.nas.execute(cmd, timeout=DELETION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "%s. Command: %s" % (str(err), cmd)
            raise Share.DeletionException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the share was deleted or not
            if self.exists(path, client):
                raise err


class FileSystemResource(FileSystemResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    file system resource.
    """
    nas_object_class = SfsFileSystem  # overrides the file system item
    display_regex = [
        re.compile(
            r"^(?P<name>[-\w]+)\s+(?P<online>[-\w]+)\s+"
            r"(?P<size>[\d\.]+[kmgtKGMT])\s+(?P<layout>[-\w]+)\s+"
            r"[-\w]+\s+[-\w]+\s+[-\w\.%]+\s+[-\w]+\s+[-\w]+\s+[-\w]+"
            r"\s*(?P<pool>[-\w]+)?$"),  # SFS 5.7P3HF3
        re.compile(
            r"^(?P<name>[-\w]+)\s+(?P<online>[-\w]+)\s+"
            r"(?P<size>[\d\.]+[kmgtKGMT])\s+(?P<layout>[-\w]+)\s+"
            r"[-\w]+\s+[-\w]+\s+[-\w\.%]+\s+[-\w]+\s+[-\w]+\s+[-\w]+"
            r"\s+[-\w]+\s*(?P<pool>[-\w]+)?$")  # SFS 5.7MP1P3
    ]

    layouts = ['mirrored', 'mirrored-stripe', 'simple', 'striped',
               'striped-mirror']
    size_regex = re.compile(r"^\s*([\d]+)\s*([%s])\s*$" %
                        UnitsSize.allowed_units_str())  # it doesn't allow dots
    invalid_pool_regex = re.compile(r".*Pool\(s\)\s+or\s+disk\(s\)\s+[-\w]+\s+"
                                    r"does\s+not\s+exist.*")
    sfshf3_already_exists_regex = re.compile(
        r".*File\s+system\s+[-\w]+\s+already\s+exists.*")
    sfsmp1p3_already_exists_regex = re.compile(
        r".*File\s+system/Rollback\s+[-\w]+\s+already\s+exists.*")
    insufficient_space_regex = re.compile(r".*Unable\s+to\s+create\s+fs\s+"
        r"[-\w]+\s+due\s+to\s+either\s+insufficient\s+space/unavailable\s+"
        r"disk\.\s+Please\s+run\s+scanbus.*")
    cannot_allocate_space_regex = re.compile(
        r".*Unable\sto\s+allocate\s+space\s+to\s+grow\s+fs\s+[-\w]+"
        r"\s+due\s+to\s+either\s+insufficient\s+space/unavailable\s+disk.*")
    must_be_online_regex = re.compile(
        r".*[-\w]+\smust\s+be\s+online\s+to\s+perform\s+grow\s+operation.*")
    already_online_regex = re.compile(r".*Filesystem\s+is\s+already\s+"
                                      r"online.*")
    usage_over_limit_regex = re.compile(
        r".*Filesystem\s+[-\w]+\s+usage\s+is\s+over\s+\d+%\.\s+If\s+the\s+"
        r"grow\s+did\s+not\s+succeed,\s+remove\s+some\s+files\s+and\s+"
        r"try\s+again.*"
    )
    rollsync_status_regex = re.compile(r"[\d\.]+%\s+Start_time\:\s+[\w/\:]+\s+"
                               r"\w+\:\s+[\d\:]+\s+Remaining_time\:\s+[\d\:]+")
    already_offline_regex = re.compile(r".*Filesystem\s+is\s+already\s+"
                                       r"offline.*")
    already_online_regex = re.compile(r".*Filesystem\s+is\s+already\s+"
                                      r"online.*")
    fs_not_exist_regex = re.compile(r".*File\s+system\s+[-\w]+\s+"
                                    r"does\s+not\s+exist.*")

    fs_get_max_number_of_attempts = 3
    fs_get_delay_between_attemps = 15

    def get_real_size_in_blocks(self, fs_name, vx_data, vx):
        """ gets the real size from "vxprint" command in blocks of 512 bytes.
        """
        try:
            return int(vx_data[fs_name]['v']['length'])
        except (KeyError, TypeError), err:
            vx.debug("ERROR while trying to get the fs %s size from parsed "
                     "vxprint data: %s." % (fs_name, err))
            return 0

    def _build_filesystems_list(self, lines):
        """ Helper to build a list of SfsFileSystemItems objects based on the
        defined "display_regex" as a regular expression for each line of
        the output of NFS.
        """
        vx = VxCommands(self.nas)
        try:
            vx_data = vx.vxprint()
        except VxCommandsException:
            vx_data = {}
        obj_list = []
        for line in [i.strip() for i in lines if i]:
            data = self.parse_displayed_line(line)
            if 'pool' in data and data['pool'] is None:
                # Sometimes the pool might be an empty value in the line output
                # because the filesystem might currently be in the process of
                # being destroyed at the same time the "storage fs list"
                # command is executed.
                self.nas.debug("The line output parsed from SFS is incomplete"
                          ", with an empty pool value. Line output: %s" % line)
            size_in_blocks = self.get_real_size_in_blocks(data['name'],
                                                          vx_data, vx)
            if not size_in_blocks:
                size_in_bytes = Size(data['size']).num_bytes
                size_in_blocks = size_in_bytes / SfsSize.block_size
                vx.debug("Using %s=%s rounded bytes from SFS display." %
                         (data['size'], size_in_blocks))
            # replace the data['size'] containing the real and display data
            data['size'] = (size_in_blocks, data['size'])
            data['online'] = data['online'] == 'online'
            obj_list.append(self._build_nas_object(**data))
        return obj_list

    def _check_size(self, size):
        """ Checks the size and raises a FileSystem.SizeException in case of
        wrong format.
        """
        if not self.size_regex.search(size):
            raise FileSystem.SizeException("Can't create fs, wrong size "
                                           "format %s." % size)

    def _check_create_errors(self, err, msg):
        if self.invalid_pool_regex.search(str(err)):
            raise Pool.DoesNotExist(msg)
        if (self.sfshf3_already_exists_regex.search(str(err)) or
                self.sfsmp1p3_already_exists_regex.search(str(err))):
            raise FileSystem.AlreadyExists(msg)
        if self.insufficient_space_regex.search(str(err)):
            raise FileSystem.InsufficientSpaceException(msg)
        raise FileSystem.CreationException(msg)

    def list(self):
        """ Returns a list of FileSystems resources items retrieved by SFS
        server.
        """
        lines = self.nas.execute("storage fs list", timeout=LISTING_TIMEOUT)
        filesystems = self._build_filesystems_list(lines[2:])
        if any([f.pool is None for f in filesystems]):
            raise NasIncompleteParsedInformation("The output information "
                "returned from SFS was incomplete, having empty values for "
                "the pool name.", filesystems)
        return filesystems

    def get(self, *args, **kwargs):
        """ Overrides the base method to do more attempts of getting the file
        system information in case the pool name is None.

        NOTE: this issue might happen in SFS when the command "storage fs list"
        is triggered at the same time a file system is destroyed. So, the line
        output becomes incomplete for that file system. The next attempts, the
        issue might not happen again.
        """

        def get(attempts):
            try:
                filesystem = super(FileSystemResource, self).get(*args,
                                                                 **kwargs)
            except NasIncompleteParsedInformation:
                if attempts < self.fs_get_max_number_of_attempts:
                    self.nas.debug('Re-attempting to retrieve information '
                                   'from SFS server about "%s" file system.' %
                                   args[0])
                    attempts += 1
                    time.sleep(self.fs_get_delay_between_attemps)  # seconds
                    filesystem = get(attempts)
                else:
                    raise
            return filesystem

        return get(0)

    def create(self, name, size, pool, layout='simple'):
        """ Creates a file system on SFS server given a fs name, size, pool and
        a layout (allowed layouts are defined on SfsFileSystem.layouts). In
        case of failures it raises properly Exceptions.
        """
        self._check_size(size)
        if layout not in self.layouts:
            raise NasException("Can't create fs, wrong '%s' layout. Available "
                         "layouts are: %s" % (layout, ', '.join(self.layouts)))
        cmd = "storage fs create %s %s %s %s" % (layout, name, size, pool)
        try:
            self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "FS creation failed: %s. Command: %s" % (str(err), cmd)
            self._check_create_errors(err, msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the file system was created or not
            if not self.exists(name):
                raise err
        vx = VxCommands(self.nas)
        try:
            vx_data = vx.vxprint()
        except VxCommandsException:
            vx_data = {}
        size_in_blocks = self.get_real_size_in_blocks(name, vx_data, vx)
        if not size_in_blocks:
            size_in_blocks = Size(size).num_bytes / SfsSize.block_size
            vx.debug("Using %s=%s rounded bytes from SFS display." %
                     (size, size_in_blocks))
        # replace the size containing the real length and display data
        size = (size_in_blocks, size)
        return self._build_nas_object(name=name, size=size, pool=pool,
                                         layout=layout, online=True)

    def delete(self, name):
        """ Deletes a SFS FileSystem given a fs name. In case of failures it
        raises a NasDeletionException.
        """
        cmd = "storage fs destroy %s" % name
        try:
            self.nas.execute(cmd, timeout=DELETION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "%s. Command: %s" % (str(err), cmd)
            raise FileSystem.DeletionException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the file system was deleted or not
            if self.exists(name):
                raise err

    def resize(self, name, size, pool=None):
        filesystem = self.get(name)
        if pool is None:
            pool = filesystem.pool
        self._check_size(size)
        size = Size(size)
        fs_tier = "primary"
        prop = self._properties(filesystem)
        if 'Tier Info' in prop:
            fs_tier = prop.get('Tier Info')

        if size > filesystem.size:
            try:
                resize_cmd = 'storage fs growto %s %s %s %s' % (fs_tier,
                    name, size, pool)
                lines = self.nas.execute(resize_cmd, timeout=CREATION_TIMEOUT)
                warning_lines = [
                    l for l in lines
                    if self.usage_over_limit_regex.search(l)]
                if warning_lines:
                    self.nas.warn('\n'.join(warning_lines))
            except NasExecCommandException, err:
                if self.cannot_allocate_space_regex.match(str(err)):
                    raise FileSystem.InsufficientSpaceException(
                        str(err))
                else:
                    raise FileSystem.ResizeException(str(err))
        elif size == filesystem.size:
            raise FileSystem.SameSizeException(
                'The size of the file system "%s" is already '
                'equal to the target size "%s".' % (name, size))
        else:
            raise FileSystem.CannotShrinkException(
                'Size of the existing file system "%s" on SFS '
                'is "%s" which is greater than the requested '
                'size "%s". Shrinking the existing file system '
                'is not supported.'
                % (name, filesystem.size, size))

    def online(self, name, online=True):
        """ Method to set the file system as online or offline.
        """
        option = "online" if online else "offline"
        cmd = "storage fs %s %s" % (option, name)
        try:
            self.nas.execute(cmd, timeout=ON_OFF_LINE_TIMEOUT)
        except NasExecCommandException as err:
            regex = self.already_online_regex if online else \
                    self.already_offline_regex
            if not regex.search(str(err)):
                msg = 'Failed to %s the file system "%s": %s. Command: %s' % \
                      (option, name, str(err), cmd)
                exc = FileSystem.OnlineException if online else \
                      FileSystem.OfflineException
                raise exc(msg)
            self.nas.debug('File system "%s" is already %s. %s' %
                           (name, option, str(err)))

    def is_restore_running(self, filesystem):
        """ Checks whether there is a rollsync task running for the given
        file system.
        """
        props = self._properties(filesystem)
        status = props.get('Rollsync Status')
        if isinstance(status, dict):
            rollsync_status = status.values()[0] \
                              if status.values() else ""
            return bool(self.rollsync_status_regex.search(rollsync_status))
        return False

    def _properties(self, name):
        """ Gets a file system properties as a dict.
        """
        cmd = "storage fs list %s" % name
        lines = []
        try:
            lines = self.nas.execute(cmd, timeout=LISTING_TIMEOUT)
        except NasExecCommandException, err:
            msg = "%s. Command: %s" % (str(err), cmd)
            if self.fs_not_exist_regex.search(str(err)):
                raise FileSystem.DoesNotExist(msg)
        parser = VxPropertiesSimpleOutputParser('\n'.join(lines))
        return parser.parse()


class DiskResource(DiskResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    disk resource.
    """
    display_regex = re.compile(r"^(?P<name>[-\w]+)\s+[-\w\s]+$")

    def list(self):
        """ Returns a list of Disk resources items retrieved by SFS server.
        """
        lines = self.nas.execute("storage disk list", timeout=LISTING_TIMEOUT)
        return self._build_nas_object_list(lines[2:])

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class PoolResource(PoolResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    pool resource.
    """
    display_regex = re.compile(r"^(?P<name>[-\w]+)\s+[-\w\s]+$")

    def list(self):
        """ Returns a list of Pool resources items retrieved by SFS server.
        """
        lines = self.nas.execute("storage pool list", timeout=LISTING_TIMEOUT)
        return self._build_nas_object_list(lines[2:])

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class CacheResource(CacheResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    cache resource.
    """
    nas_object_class = SfsCache  # overrides the snapshot object

    display_regex = re.compile(r"^(?P<name>[-\w]+)\s+(?P<size>[\-\d]+)\s+"
                               r"(?P<used>[\-\d]+)\s+(\(\d+\)|\-)\s+"
                               r"(?P<available>[\-\d]+)\s+(\(\d+\)|\-)\s+"
                               r"(?P<snapshot_count>[\-\d]+)$")

    already_exists_regex = re.compile(r".*Cache\s+object\s+[-\w]+\s+already\s+"
                                      r"exists.*")
    does_not_exist_regex = re.compile(r".*cache\s+object\s+[-\w]+\sdoes\s+not"
                                      r"\s+exist.*")
    invalid_pool_regex = re.compile(r".*Pool\(s\)\s+or\s+disk\(s\)\s+[-\w]+\s+"
                                    r"does\s+not\s+exist.*")
    cannot_allocate_space_regex = re.compile(r".*Cannot\s+allocate\s+space\s+"
                                 r"to\s+grow\s+volume\s+to\s+(\d+)\s+blocks.*")
    insufficient_space_regex = re.compile(r".*Unable\s+to\s+create\s+fs\s+"
        r"[-\w]+\s+due\s+to\s+either\s+insufficient\s+space/unavailable\s+"
        r"disk\.\s+Please\s+run\s+scanbus.*")
    minimum_allowed_size = Size('5M')

    def _get_caches(self, output):
        return self._build_nas_object_list(output[1:])

    def list(self):
        """ Returns a list of Cache resources items retrieved by SFS server.

        NOTE: display_regex values like "-" means an empty value in
        Cache Object perspective. It usually happens when the caches are being
        listed in the same time as some cache is being deleted. The line output
        for that cache becomes incomplete for some tiny time, maybe 1 second,
        with empty values "-". Below in the code, we treat those values as
        emtpy setting them as None. Thus, the NasIncompleteParsedInformation
        is raised with the caches list.
        """
        lines = self.nas.execute("storage rollback cache list",
                                 timeout=LISTING_TIMEOUT)
        caches = self._get_caches(lines)
        attrs = ['name', 'size', 'used', 'available', 'snapshot_count']
        for cache in caches:
            for attr in attrs:
                value = getattr(cache, attr)
                if isinstance(value, str) and value.strip() == '-':
                    setattr(cache, attr, None)
        if any([any([getattr(f, a) is None for a in attrs]) for f in caches]):
            raise NasIncompleteParsedInformation("The output information "
                "returned from SFS was incomplete, having some empty values "
                "for cache object information.", caches)
        return caches

    def _build_nas_object(self, **kwargs):
        """ Overrides this to gets the correct size.
        """
        klass = self.nas_object_class  # pylint:disable=I0011,E1102
        dash_to_zero = lambda s: 0 if s == '-' else s
        # because SFS only shows the number without unit in MB.
        kwargs['size'] = "%sM" % dash_to_zero(kwargs['size'])
        kwargs['used'] = dash_to_zero(kwargs['used'])
        kwargs['available'] = dash_to_zero(kwargs['available'])
        return klass(self, **kwargs)  # pylint:disable=I0011, E1102

    def _check_size(self, size):
        """ Checks the size and raises a Cache.SizeException in case of a wrong
        format or if it is less than the minimum allowed size.
        """
        if not FileSystemResource.size_regex.search(size):
            raise Cache.SizeException("Can't create cache object, wrong size "
                                      "format %s." % size)
        if Size(size) < self.minimum_allowed_size:
            raise Cache.SizeException("Can't create cache object, size cannot "
                                "be less than %s." % self.minimum_allowed_size)

    def create(self, name, size, pool):
        """ Creates a Cache with a given name, size and poll name.
        """
        self._check_size(size)
        cmd = "storage rollback cache create %s %s %s" % (name, size, pool)
        try:
            self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "Cache object creation failed: %s. Command: %s" % (str(err),
                                                                     cmd)
            if self.invalid_pool_regex.search(str(err)):
                raise Pool.DoesNotExist(msg)
            if self.insufficient_space_regex.search(str(err)):
                raise Cache.InsufficientSpaceException(msg)
            if self.already_exists_regex.search(str(err)):
                cmd2 = "storage rollback cache list"
                stdout = self.nas.execute(cmd2, timeout=LISTING_TIMEOUT)
                if name in str(stdout):
                    raise Cache.AlreadyExists(msg)
                else:
                    self.nas.debug("Cache creation failed due to left " \
                                   "over underlying volumes of cache. " \
                                   "sfs error message : %s" % err)
                    vx2 = VxCommands(self.nas)
                    vx2.vxedit(name)
                    self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
                    self.nas.debug("Underlying cache volume deleted " \
                                   " and created the cache")
                    return
            raise Cache.CreationException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the cache was created or not
            if not self.exists(name):
                raise err
        return self.get(name)

    def delete(self, name):
        """ Deletes a SFS cache object given a cache name. In case of failures
        it raises a NasDeletionException.
        """
        cmd = "storage rollback cache destroy %s" % name
        try:
            self.nas.execute(cmd, timeout=DELETION_TIMEOUT)
            vx1 = VxCommands(self.nas)
            stdout1 = vx1.vxprint_simple()
            if name in stdout1:
                vx2 = VxCommands(self.nas)
                vx2.vxedit(name)
                self.nas.debug("Identified the underlying cache" \
                               " volumes left over and deleted.")
        except NasExecCommandException, err:
            msg = "%s. Command: %s" % (str(err), cmd)
            if self.does_not_exist_regex.search(str(err)):
                raise Cache.DoesNotExist(msg)
            raise Cache.DeletionException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the cache was deleted or not
            if self.exists(name):
                raise err

    def resize(self, name, size, pool=None):
        """ Resizes a Cache object given a cache name and the new size.
        """
        self._check_size(size)
        cache = self.get(name)
        size = Size(size)
        if size > cache.size:
            try:
                vx = VxCommands(self.nas)
                vx.cache_grow(name, size)
            except VxCommandsException, err:
                match = self.cannot_allocate_space_regex.match(str(err))
                if match:
                    blocks = match.groups()[0]
                    size = Size("%sK" % (int(blocks) * 2))
                    raise Cache.InsufficientSpaceException(str(err), size)
                raise Cache.ResizeException(str(err))
        elif size == cache.size:
            raise Cache.SameSizeException('The size of the cache object "%s" '
                                          'is already equal to the target '
                                          'size "%s".' % (name, size))
        else:
            raise Cache.CannotShrinkException("Shrinking cache objects is not "
                                              "supported.")

    def get_related_snapshots(self, name):
        """ Returns a list of snapshots names that is related to the cache.
        """
        snapshots = []
        process = None
        cmd = "storage rollback cache list {0}".format(name)
        lines = self.nas.execute(cmd, timeout=LISTING_TIMEOUT)
        for line in lines:
            if process:
                snapshots.append(line.strip())
            if line.startswith("rollbacks located on cache"):
                process = True
        return snapshots


class SnapshotResource(SnapshotResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
        snapshot resource.
    """
    nas_object_class = SfsSnapshot

    display_regex = re.compile(r"^(?P<name>[-\w]+)\s+(?P<snaptype>[\w]+)\s+"
                               r"(?P<filesystem>[-\w]+)\s+"
                               r"(?P<date>\d+/\d+/\d+\s\d+:\d+)$")
    rollsync_status_regex = re.compile(r"[\d\.]+%\s+Start_time\:\s+[\w/\:]+\s+"
                               r"\w+\:\s+[\d\:]+\s+Remaining_time\:\s+[\d\:]+")
    already_exists_regex = re.compile(r".*Rollback\s+[-\w]+\s+already\s+exist"
                                      r"\s+for\s+file\s+system\s+[-\w]+\.")
    sfshf3_snapshot_not_exist_regex = re.compile(r".*Rollback\s+[-\w]+\s+does "
                                    r"not exist for file system\s+[-\w]+\.")
    # SFS rollback ERROR V-288-3075 Specified rollback L_2480-fs1_test01_
    # does not exist. This error message will cover also ISA 7.1
    sfsmp1p3_snapshot_not_exist_regex = re.compile(r".*Specified rollback"
                                                r"\s+[-\w]+\s+does not exist.")
    fs_not_exist_regex = re.compile(r".*File\s+system\s+[-\w]+\s+"
                                    r"does\s+not\s+exist")
    cache_not_exist_regex = re.compile(r".*cache\s+object\s+[-\w]+\s+"
                                       r"does\s+not\s+exist.*")
    restore_failed1_regex = re.compile(r".*restore\s+from\s+rollback\s+"
                                       r"(?P<name>[-\w]+)\s+failed.*")
    restore_failed2_regex = re.compile(r".*Unable\s+to\s+restore\s+file\s+"
                                       r"system\s+(?P<filesystem>[-\w]+)\s+"
                                       r"with\s+rollback\s+(?P<name>[-\w]+).*")
    restore_ongoing_regex = re.compile(r".*Rollback\s+restore\s+operation\s+"
                                       r"failed\s+as\s+rollback\s+sync\s+is\s+"
                                       r"already\s+in\s+progress\s+for\s+"
                                       r"[-\w]+.*")
    destroy_failed_online_regex = re.compile(r".*Rollback\s+destroy\s+"
                                    r"operation\s+failed\s+as\s+[-\w]+\s+is\s+"
                                    r"in\s+online\s+state,\s+run\s+offline\s+"
                                    r"first.*")
    fsck_failed_regex = re.compile(r".*fsck\s+failed\s+for\s+[-\w]+.*")
    destroy_failed_restore_ongoing_regex = re.compile(r".*Rollback\s+[-\w]+\s"
                                    r"dissociate\s+failed.*")

    def _get_snapshots(self, output):
        return self._build_nas_object_list(output[1:])

    def list(self):
        """ Returns a list of snapshot resources items retrieved by SFS server.
        """
        lines = self.nas.execute("storage rollback list",
                                 timeout=LISTING_TIMEOUT)
        return self._get_snapshots(lines)

    def rollbackinfo(self, name):
        """ Returns the info of snapshot resources.
        """
        cmd = "storage rollback list %s" % (name)
        output = self.nas.execute(cmd, timeout=LISTING_TIMEOUT)
        return output

    def create(self, name, filesystem, cache):
        """ Creates a snapshot (rollback) on SFS server given a snapshot name,
        file system name and a cache object name. In case of failures it raises
        relevant Exception.
        """
        snaptype = 'space-optimized'
        cmd = "storage rollback create %s %s %s %s" % (snaptype, name,
                                                       filesystem, cache)
        try:
            self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
        except NasExecCommandException, err:
            msg = "Snapshot creation failed: %s Command: %s" % (str(err), cmd)
            if self.already_exists_regex.search(str(err)):
                raise Snapshot.AlreadyExists(msg)
            if self.fs_not_exist_regex.search(str(err)):
                raise FileSystem.DoesNotExist(msg)
            if self.cache_not_exist_regex.search(str(err)):
                raise Cache.DoesNotExist(msg)
            if self.fsck_failed_regex.search(str(err)):
                cache_obj = self.nas.cache.get(cache)
                if not cache_obj.available:
                    msg = 'Failed to create the snapshot "%s" for the file ' \
                          'system "%s" because the cache "%s" is full. ' \
                          '%s' % (name, filesystem, cache, msg)
                    raise Snapshot.CreationException(msg)
            raise Snapshot.CreationException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the snapshot (Rollback) was created or not
            if not self.exists(name):
                raise err
        return self._build_nas_object(name=name, filesystem=filesystem,
                                      cache=cache, snaptype=snaptype)

    def delete(self, name, filesystem):
        """ Deletes a SFS snapshot given a snapshot name and fs name.
        In case of failures it raises a Snapshot.DeletionException.
        """
        cmd = "storage rollback destroy {0} {1}".format(name, filesystem)
        try:
            self.nas.execute(cmd, timeout=DELETION_TIMEOUT)
        except NasExecCommandException, err:
            if 'ERROR V-288-2027' in str(err):
                self.nas.debug("rollback not deleted, trying to delete it. " \
                               "sfs error message: %s" % err)
                self.nas.execute('storage fs destroy %s' % name)
                self.nas.debug("rollback deleted successfully")
            if self.destroy_failed_restore_ongoing_regex.search(str(err)):
                msg = "Snapshot deletion failed: %s. Unable to destroy " \
                      "snapshot while restore snapshot " \
                      "process is in progress. Command: %s" % (err, cmd)
                raise Snapshot.RollsyncRunning(msg)
            msg = "Snapshot deletion failed: %s. Command: %s" % (str(err), cmd)
            if self.destroy_failed_online_regex.search(str(err)):
                self.nas.warn('Attempting to offline the snapshot "%s" before '
                            'deleting it. SFS error message: %s' % (name, msg))
                cmd_offline = "storage rollback offline %s" % name
                try:
                    self.nas.execute(cmd_offline, timeout=ON_OFF_LINE_TIMEOUT)
                except NasExecCommandException, err:
                    msg = "%s. Offline action: %s. Command: %s" % (msg,
                                                         str(err), cmd_offline)
                    raise Snapshot.DeletionException(msg)
                try:
                    # try to delete again
                    self.nas.execute(cmd, timeout=CREATION_TIMEOUT)
                    return
                except NasExecCommandException, err:
                    # just pass to try to get the errors below
                    pass
            if self.fs_not_exist_regex.search((str(err))):
                raise FileSystem.DoesNotExist(msg)
            if (self.sfshf3_snapshot_not_exist_regex.search(str(err)) or
                    self.sfsmp1p3_snapshot_not_exist_regex.search(str(err))):
                raise Snapshot.DoesNotExist(msg)
            raise Snapshot.DeletionException(msg)
        except NasExecutionTimeoutException, err:
            # maybe the SSH connection was dropped and would be worth to check
            # whether the snapshot (Rollback) was deleted or not
            if self.exists(name):
                raise err

    def restore(self, name, filesystem):
        """ Restores the file system given a snapshot name and the file system.
        In SFS, to restore a file system, 3 steps are needed:
         1. offline the file system if it is online;
         2. restore the file system;
         3. bring the file system back to the online state.
        """
        def try_online():
            # we need to bring the file system online back again
            self.nas.debug('Restore failed, trying to online the file system '
                           '"%s"' % filesystem)
            try:
                self.nas.filesystem.online(filesystem)
            except NasException as err:
                self.nas.warn('Failed to online the file system "%s" after a '
                              'failed restore. %s' % (filesystem, str(err)))

        base_err = "File system failed to restore: %s"

        # step 1: offline the file system
        try:
            self.nas.filesystem.online(filesystem, False)
        except FileSystem.OfflineException as err:
            raise FileSystem.OfflineException(base_err % str(err))

        # step 2: restore the file system
        restore_cmd = "storage rollback restore %s %s" % (filesystem, name)
        env = dict(SNAPSHOT_RESTORE_CONFIRM='YES')
        try:
            self.nas.execute(restore_cmd, timeout=CREATION_TIMEOUT, env=env)
        except NasExecCommandException as err:
            msg = base_err % ("%s. Command: %s" % (str(err), restore_cmd))
            if self.restore_failed1_regex.search(str(err)) or \
               self.restore_failed2_regex.search(str(err)):
                # check first whether a restore is currently being executed
                if (self.restore_ongoing_regex.search(str(err)) or
                        self.nas.filesystem.is_restore_running(filesystem)):
                    # If the restore failed because the rollsync task was
                    # running, and we try to  online the file system before
                    # checking "is_restore_running", the online action might
                    # take a bit time to complete and the rollsync might finish
                    # quickly and the exception Snapshot. RollsyncRunning won't
                    # be raised. That's why we are trying to online the file
                    # system afterwards in the statement below and not before.
                    try_online()
                    raise Snapshot.RollsyncRunning(msg)
            # try to bring the file system back again
            try_online()
            if self.fs_not_exist_regex.search(str(err)):
                raise FileSystem.DoesNotExist(msg)
            if (self.sfshf3_snapshot_not_exist_regex.search(str(err)) or
                    self.sfsmp1p3_snapshot_not_exist_regex.search(str(err))):
                raise Snapshot.DoesNotExist(msg)
            raise Snapshot.RestoreException(msg)

        # step 3: online the file system back
        try:
            self.nas.filesystem.online(filesystem)
        except FileSystem.OnlineException as err:
            raise FileSystem.OnlineException(base_err % str(err))
