##############################################################################
# COPYRIGHT Ericsson AB 2016
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,E1101

import re
from ..sfs.resources import ShareResource as SfsShareResource
from ..sfs.resources import FileSystemResource as SfsFileSystemResource
from ..sfs.resources import DiskResource as SfsDiskResource
from ..sfs.resources import PoolResource as SfsPoolResource
from ..sfs.resources import CacheResource as SfsCacheResource
from ..sfs.resources import SnapshotResource as SfsSnapshotResource
from ..sfs.resources import LISTING_TIMEOUT
from ...drivers.va.objects import VaFileSystem
from ...objects import Pool, FileSystem
from ...nasexceptions import NasUnexpectedOutputException
from ..sfs.utils import VxCommands, VxCommandsException
from ..sfs.parsers import VxPropertiesOutputParser


class ShareResource(SfsShareResource):

    def create(self, path, client, options):
        ops = set(options if hasattr(options, '__iter__')
                          else options.split(','))
        ops.add('nordirplus')
        return super(ShareResource, self).create(path, client, ops)

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
        va_fix_regex = r"^(?P<name>[/\w:-]+)\s+(?P<client>[\d\.\*/]+)" \
                        r"\s*(\((?P<options>[\w,]+)\))*$"
        line_start = ""
        for line in [i.strip() for i in lines if i]:
            if line_start != "":
                line = line_start + " " + line
                line_start = ""
            if self.display_regex.match(line):
                data = self.parse_displayed_line(line)
                data['faulted'] = (self.faulted_match_format % data) in faulted
                if data['client'] == "*":
                    data['client'] = ""
                obj_list.append(self._build_nas_object(**data))
            elif re.match(va_fix_regex, line):
                line_start = line
            else:
                raise NasUnexpectedOutputException('It\'s not possible to '
                                                   'parse the output of '
                                                   'faulted shares received'
                                                   ' from %s. Line output: '
                                                   '"%s".' % (str(self.nas),
                                                              line))
        return obj_list


class FileSystemResource(SfsFileSystemResource):

    nas_object_class = VaFileSystem
    display_regex = re.compile(
        r"^(?P<name>[-\w]+)\s+(?P<online>[-\w]+)\s+"
        r"(?P<size>[\d\.]+[kmgtKGMT])\s+(?P<layout>[-\w]+)\s+"
        r"[-\w]+\s+[-\w]+\s+[-\w\.%]+\s+[\.\w]*\s*[-\w]+\s+[-\w]+\s+[-\w]+"
        r"\s+[-\w]+\s*[-\w]*\s*$")  # No information about pools in ISA 7.1

    isa_already_exists_regex = re.compile(
        r".*File\s+system\s+already\s+exists.*")
    already_offline_regex = re.compile(
        r".*Filesystem\s+[-\w]+\s+is\s+already\s+offline.*")

    def _check_create_errors(self, err, msg):
        if self.invalid_pool_regex.search(str(err)):
            raise Pool.DoesNotExist(msg)
        if self.isa_already_exists_regex.search(str(err)):
            raise FileSystem.AlreadyExists(msg)
        if self.insufficient_space_regex.search(str(err)):
            raise FileSystem.InsufficientSpaceException(msg)
        raise FileSystem.CreationException(msg)

    def list(self):
        """ Returns a list of FileSystems resources items retrieved by ISA
        server.
        """
        lines = self.nas.execute("storage fs list", timeout=LISTING_TIMEOUT)
        filesystems = self._build_filesystems_list(lines[2:])
        return filesystems

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
        else:
            try:
                vx_data = self.vtask_list().values()
                for list_item in vx_data:
                    if "SNAPSYNC" in list_item:
                        return True
                return False
            except VxCommandsException:
                return False

    def vtask_list(self):
        vx = VxCommands(self.nas)
        output = vx.execute('vxtask list')
        parser = VxPropertiesOutputParser(output)
        return parser.parse()


class DiskResource(SfsDiskResource):
    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class PoolResource(SfsPoolResource):
    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class CacheResource(SfsCacheResource):

    display_regex = re.compile(r"^(?P<name>[-\w]+)\s+(?P<size>[\-\d]+)\s+"
                           r"(?P<used>[\-\d]+)\s+\([\d\.\-]+\)\s+"
                           r"(?P<available>[\-\d]+)\s+\([\d\.\-]+\)\s+"
                           r"(?P<snapshot_count>[\-\d]+)$")

    def _get_caches(self, output):
        return self._build_nas_object_list(output[2:])

    def get_related_snapshots(self, name):
        """ Returns a list of snapshots names that is related to the cache
        on the ISA server as the output is different from SFS.
        """
        snapshots = []
        process = None
        cmd = "storage rollback cache list {0}".format(name)
        lines = self.nas.execute(cmd, timeout=LISTING_TIMEOUT)
        for line in lines:
            if process:
                snapshots.append(line.strip())
            if line.startswith("============"):
                process = True
        return snapshots


class SnapshotResource(SfsSnapshotResource):

    restore_ongoing_regex = re.compile(r".*Rollback\s+restore\s+operation\s+"
                                       r"failed\s+as\s+rollback\s+sync\s+is\s+"
                                       r"in\s+progress\s+for\s+[-\w]+.*")

    def _get_snapshots(self, output):
        return self._build_nas_object_list(output[2:])
