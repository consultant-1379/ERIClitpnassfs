##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,W0223,W0221
""" This module contains the base classes for NAS resources. There are at least
7 basic resources for NAS:

 - NasFileSystemBase;
 - NasShareBase;
 - NasDiskBase;
 - NasPoolBase;
 - NasCacheBase;
 - NasSnapshotBase;
 - NasServerBase.

Each resource depends on its corresponding NasResourceItem implemented on
the resourceitems module.
"""

from abc import ABCMeta, abstractmethod

from .nasexceptions import NasImplementationError, \
    NasUnexpectedOutputException, NasIncompleteParsedInformation
from .objects import Share, FileSystem, Disk, Pool, Cache, Snapshot, NasServer


class ResourceBase(object):
    """ Abstract class for a base class for NAS resources.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = None
    nas_object_class = None
    display_regex = None

    def __init__(self, nas):
        r""" Base constructor for the ResourceBase class. Every subclass of
        of ResourceBase must have the nas_object_class attribute properly
        specified with the corresponding NasResourceItem from resourceitems
        module. The first argument must be an instance of NasBase subclass.

        >>> class MyResource(ResourceBase):
        ...     def create(self, *args, **kwargs):
        ...         pass
        ...     def list(self, *args, **kwargs):
        ...         pass
        ...     def get(self, *args, **kwargs):
        ...         pass
        ...     def exists(self, *args, **kwargs):
        ...         pass
        ...     def delete(self, *args, **kwargs):
        ...         pass
        >>> try:
        ...     MyResource(None)
        ... except Exception, err:
        ...     pass
        ...
        >>> isinstance(err, NasImplementationError)
        True
        >>> str(err)
        'nas_object_class must be properly set for this NasResource class.'
        >>> MyResource.nas_object_class = Share
        >>> MyResource(None)
        <MyResource>
        """
        if self.nas_object_class is None:
            raise NasImplementationError("nas_object_class must be properly"
                                         " set for this NasResource class.")
        self._nas = nas

    def __repr__(self):
        """ Returns the representative string of this object.
        """
        return "<%s>" % self.__class__.__name__

    @property
    def nas(self):
        """ Property to access the nas instance of the NasBase subclass, that
        is, its parent instance.
        """
        return self._nas

    def parse_displayed_line(self, line):
        """ Uses the defined cls.display_regex to parse a line from a generic
        output.
        """
        if isinstance(self.display_regex, list):
            match = None
            for regex in self.display_regex:
                match = regex.match(line)
                if match:
                    break
        else:
            match = self.display_regex.match(line)
        if not match:
            raise NasUnexpectedOutputException('It\'s not possible to parse '
                'the output received from %s, as it may be corrupted. Line '
                'output: "%s".' % (str(self.nas), line))
        return match.groupdict()

    def _build_nas_object_list(self, lines):
        r""" Helper to build a list of ResourceItems objects based on the
        defined "display_regex" as a regular expression for each line of
        the output of NFS.
        >>> import re
        >>> class MyResource(ResourceBase):
        ...     nas_object_class = Share
        ...     display_regex = re.compile(r"^(?P<name>[/\w-]+)\s+(?P<client>"
        ...                          r"[\w\.\*/]+)\s+\((?P<options>[\w,]+)\)$")
        ...     def create(self, *args, **kwargs):
        ...         pass
        ...     def list(self, *args, **kwargs):
        ...         pass
        ...     def get(self, *args, **kwargs):
        ...         pass
        ...     def exists(self, *args, **kwargs):
        ...         pass
        ...     def delete(self, *args, **kwargs):
        ...         pass
        ...
        >>> class Nas(object):
        ...     def __str__(self):
        ...         return 'NAS'
        ...     def debug(self, msg):
        ...         pass
        ...
        >>> res = MyResource(Nas())
        >>> res
        <MyResource>
        >>> res._build_nas_object_list(['/v/s1 123 (rw)', '/v/s2 345 (ro)'])
        [<Share /v/s1 123>, <Share /v/s2 345>]
        >>> try:
        ...     res._build_nas_object_list(['foo wrong'])
        ... except Exception, err:
        ...     pass
        ...
        >>> isinstance(err, NasUnexpectedOutputException)
        True
        """
        obj_list = []
        for line in [i.strip() for i in lines if i]:
            data = self.parse_displayed_line(line)
            obj_list.append(self._build_nas_object(**data))
        return obj_list

    def _build_nas_object(self, **kwargs):
        """ Helper to properly instantiate a generic ResourceItem defined on
        nas_object_class attribute.
        """
        klass = self.nas_object_class  # pylint:disable=I0011,E1102
        return klass(self, **kwargs)  # pylint:disable=I0011, E1102

    def _build_identifier_dict(self, *args, **kwargs):
        identifier_keys = self.nas_object_class.identifier_keys
        given = (len(args) + len(kwargs))
        takes = len(identifier_keys)
        if given != takes:
            plural = "s" if takes > 1 else ""
            raise TypeError("This method takes exactly %s argument%s "
                            "(%s given)" % (takes, plural, given))
        diff = set(kwargs.keys()) - set(identifier_keys)
        if diff:
            name = self._base_attr_name  # pylint: disable=I0011,E1101
            raise TypeError("The following arguments are not identifiers for a"
                            "%s: %s. The expected identifiers are: %s" %
                           (name, ', '.join(diff), ', '.join(identifier_keys)))
        identifier = dict(zip(identifier_keys, args))
        identifier.update(kwargs)
        return identifier

    @abstractmethod
    def list(self):
        """ Base method to list NasResourceItems on a generic server.
        @return: list of NasResourceItem objects
        """

    @abstractmethod
    def create(self, *args, **kwargs):
        """ Base method to create a NasResourceItem on a generic server.
        @return: NasResourceItem
        """

    @abstractmethod
    def delete(self, *args, **kwargs):
        """ Base method to delete a NasResourceItem on a generic server.
        @return: None
        """

    def get(self, *args, **kwargs):
        """ Gets a generic resource item from NAS server given an identifier
        as arguments.
        """
        identifier = self._build_identifier_dict(*args, **kwargs)
        try:
            objects = self.list()
        except NasIncompleteParsedInformation as err:
            objects = err.parsed_data
        try:
            item = [s for s in objects if all([getattr(s, i) == v for
                                               i, v in identifier.items()])][0]
        except IndexError:
            ident = ', '.join(identifier.values())
            name = self._base_attr_name  # pylint: disable=I0011,E1101
            msg = 'The "%s" %s does not exist in %s.' % (ident, name,
                                                         self.nas.name)
            raise self.nas_object_class.DoesNotExist(msg)
        missing = [a for a in item.non_lazy_attributes
                   if getattr(item, a) is None]
        if missing:
            msg = 'The parsed output information from %s is incomplete, ' \
                  'missing the following value(s): %s'
            raise NasIncompleteParsedInformation(msg % (self.nas.name,
                                                        '\n'.join(missing)),
                                                 item)
        return item

    def exists(self, *args, **kwargs):
        """ Checks whether a generic resource item on SFS server exists or not
        given an identifier as arguments.
        """
        try:
            self.get(*args, **kwargs)
        except self.nas_object_class.DoesNotExist:
            return False
        return True


###############################################################################
# base Nas class for storage resources like FileSystems, Disks, Caches, etc.


class NasResourceStorageBase(ResourceBase):
    """ Every NAS resource characterized as a storage, should inherit this
    class, for example: NasFileSystemBase, NasCacheBase, etc.

    This class mainly includes the method resize in the interface.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def resize(self, name, size, pool=None):
        """ Base method to resize a NAS storage resource.
        @return: None
        """


###############################################################################
# base resources implementation below


class PoolResourceBase(ResourceBase):
    """ This is the base class for a Pool resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "pool"
    nas_object_class = Pool

    @abstractmethod
    def create(self, name):
        """ Abstract method to create pools.
        """

    @abstractmethod
    def delete(self, name):
        """ Abstract method to delete pools.
        """


class DiskResourceBase(ResourceBase):
    """ This is the base class for a Disk resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "disk"
    nas_object_class = Disk

    @abstractmethod
    def create(self, name):
        """ Abstract method to create disks.
        """

    @abstractmethod
    def delete(self, name):
        """ Abstract method to delete disks.
        """


class FileSystemResourceBase(NasResourceStorageBase):
    """ This is the base class for a FileSystem resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "filesystem"
    nas_object_class = FileSystem

    @abstractmethod
    def create(self, name, size, pool, layout='simple'):
        """ Abstract method to create file systems.
        """

    @abstractmethod
    def delete(self, name):
        """ Abstract method to delete file systems.
        """

    @abstractmethod
    def online(self, name, online=True):
        """ Abstract method to sets the file system as online or offline.
        """

    @abstractmethod
    def is_restore_running(self, filesystem):
        """ Abstract method to check if a restore is in progress for the given
        file system.
        """


class ShareResourceBase(ResourceBase):
    """ This is the base class for a Share resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "share"
    nas_object_class = Share

    @abstractmethod
    def create(self, name, client, options):
        """ Abstract method to create shares.
        """

    @abstractmethod
    def delete(self, name, client):
        """ Abstract method to delete shares.
        """


class CacheResourceBase(NasResourceStorageBase):
    """ This is the base class for a Cache resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "cache"
    nas_object_class = Cache

    @abstractmethod
    def create(self, name, size, pool):
        """ Abstract method to create caches.
        """

    @abstractmethod
    def delete(self, name):
        """ Abstract method to delete caches.
        """

    @abstractmethod
    def get_related_snapshots(self, name):
        """ Returns a list of snapshots names that is related to the cache.
        """


class SnapshotResourceBase(ResourceBase):
    """ This is the base class for a Rollback resource of a NFS server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "snapshot"
    nas_object_class = Snapshot

    @abstractmethod
    def create(self,  name, filesystem, cache):
        """ Abstract method to create snapshots.
        """

    @abstractmethod
    def delete(self, name, filesystem):
        """ Abstract method to delete snapshots.
        """

    @abstractmethod
    def restore(self, name, filesystem):
        """ Abstract method to restore snapshots.
        """


class NasServerResourceBase(ResourceBase):
    """ This is the base class for a UnityXT NAS Server.
    """
    __metaclass__ = ABCMeta
    _base_attr_name = "nasserver"
    nas_object_class = NasServer

    @abstractmethod
    def create(self, name, pool, ports, network, protocols, ndmp_pass):
        """ Abstract method to create NAS Servers.
        ports parameter is comma separated string, e.g. "0,2".
        network parameter is a comma separated string which must have
        4 fields "sp,ip,netmask,gateway".
        """

    @abstractmethod
    def delete(self, name):
        """ Abstract method to delete NAS Servers.
        """

    @abstractmethod
    def list(self):
        """ Returns a list of NAS Servers.
        """

    @abstractmethod
    def get_nasserver_details(self, name):
        """ Returns details of a NAS Server.
        """
