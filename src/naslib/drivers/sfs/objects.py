##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains implemention some special resource items for SFS
such as: SfsFileSystem, SfsCache and SfsSnapshot. They inherit
respectively from FileSytem, Cache and Snapshot and overrides or add new
special features.
"""

from ...objects import FileSystem, Snapshot, Cache, Pool
from ...baseobject import Attr, LazyAttr

from .resourceprops import SfsSize
from .utils import VxCommands, VxCommandsException


class SfsFileSystem(FileSystem):
    """ File system item for SFS. It's begin inherited mainly because of
    file system sizes comparison, as SFS always displays the size in nas
    console rounded. SFS also rounds the size up to the multiple of the
    disk group alignment that the file system belongs to.
    """

    def __init__(self, resource, name, size, layout, pool, online):
        """ File systems of SFS are displayed with sizes in a human readable
        format, so we'll override the constructor and use SfsSize object as
        the size attribute.
        """
        real_size_in_blocks, display_size = size
        super(SfsFileSystem, self).__init__(resource, name, display_size,
                                            layout, pool, online)
        self.size = Attr(SfsSize(real_size_in_blocks, display_size, self))
        self.display_size = display_size
        self._size_in_blocks = None
        self._disk_alignment = None
        self._properties = None
        self.vx = VxCommands(resource.nas)

    @property
    def properties(self):
        """ Retrieves properties related to this file system coming from
        vxprint command output.
        """
        if self._properties is None:
            self.vx.debug("Getting the %s fs properties from vxprint" %
                          self.name)
            try:
                vxprint_data = self.vx.vxprint()
            except VxCommandsException:
                return {}
            try:
                self._properties = vxprint_data[self.name]
            except KeyError:
                self.vx.debug("The %s fs not found in vxprint output" %
                              self.name)
                return {}
        return self._properties

    @property
    def disk_alignment(self):
        """ Returns the disk alignment size of the disk group from the
        following commands output: vxdisk and vxdg.
        """
        if self._disk_alignment is not None:
            return self._disk_alignment
        self.vx.debug("Getting the disk group alignment of fs %s" % self.name)
        props = self.properties
        if not props:
            self.vx.debug("Error while trying to get the %s fs properties "
                          "through vxprint. Using %s bytes as default size "
                          "alignment." % (self.name, SfsSize.block_size))
            return SfsSize.block_size

        try:
            disk = props['sd'][0]['name'].split('-')[0]
        except (KeyError, IndexError) as err:
            self.vx.debug("Error while trying to get the 'sd' information "
                          "through vxprint: %s. Using %s bytes as default "
                          "size alignment." % (str(err), SfsSize.block_size))
            return SfsSize.block_size

        try:
            self.vx.debug("Getting the disk group id of fs %s" % self.name)
            group_id = self.vx.get_disk_group_id(disk)
            self.vx.debug("Getting the %s disk group properties of fs %s" %
                          (group_id, self.name))
            props = self.vx.get_group_properties(group_id)
            if 'alignment' not in props:
                self.vx.debug("Error while trying get the alignment size from "
                              "disk group properties of fs %s. Using %s bytes "
                              "as default." % (self.name, SfsSize.block_size))
                return SfsSize.block_size
            self.vx.debug("Parsing the alignment %s" % props['alignment'])
            alignment_str = "%s %s" % tuple(props['alignment'])
            match = self.vx.align_regex.match(alignment_str)
            if not match:
                self.vx.debug("Error while trying to parse the alignment size "
                              "of fs %s. Using %s bytes as default." %
                              (self.name, SfsSize.block_size))
                return SfsSize.block_size
            alignment = match.groups()[0]
        except VxCommandsException:
            self.vx.debug("Error while trying to retrieve the alignment size "
                          "of fs %s. Using %s bytes as default." % (self.name,
                          SfsSize.block_size))
            return SfsSize.block_size
        self._disk_alignment = int(alignment)
        return self._disk_alignment


class SfsCache(Cache):

    def __init__(self, resource, name, size, pool=None, used=None,
                 available=None, snapshot_count=None):
        """ Cache object for SFS has to have specific functionality as the
        list provided by the nas console doesn't show the proper pools or disks
        related to the caches.
        """
        super(SfsCache, self).__init__(resource,  name, size, pool, used,
                                       available, snapshot_count)
        self.pool = LazyAttr(pool, self.get_pool)

    def get_pool(self):
        """ Retrieves a Pool object related to this cache object by parsing
        information from the output of the vxprint command on SFS.
        """
        vx = VxCommands(self.resource.nas)
        return Pool(self.resource, vx.get_pool_by_cache(self.name))


class SfsSnapshot(Snapshot):

    def __init__(self, resource, name, filesystem, cache=None,
                 snaptype=None, date=None):
        """ Snapshot (rollback) for SFS has to have specific functionality as
        the list provided doesn't show the cache related to the snapshot.
        """
        super(SfsSnapshot, self).__init__(resource, name, filesystem,
                                          cache, snaptype, date)
        self.cache = LazyAttr(cache, self.get_cache)

    def get_cache(self):
        """ Returns a Cache object through the get_related_snapshots() method.
        """
        for cache in self.resource.nas.cache.list():
            snapshots = cache.get_related_snapshots()
            for snapshot in snapshots:
                if snapshot == self.name:
                    return cache
