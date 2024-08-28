##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,E1101
""" This module contains the basic classes for NAS objects like:

 - FileSystem;
 - Share;
 - Disk;
 - Pool;
 - Cache;
 - Snapshot;
 - NasServer.

"""

from .resourceprops import StringOptions, Size
from .baseobject import NasObject, NasStorageObject, Attr, ExclusiveExceptions
from .nasexceptions import NasException


class Share(NasObject, ExclusiveExceptions):
    """ NasObject class to abstract Share instances of a NAS.
    """
    identifier_keys = ('name', 'client')

    def __init__(self, resource, name, client, options, faulted=False):
        """ The NAS Share object also has a client and options as basic
        attributes.
        """
        super(Share, self).__init__(resource, name)
        self.client = Attr(client)
        self.options = Attr(StringOptions(options))
        self.faulted = faulted

    def __repr__(self):
        """ Returns the representation string of this object.
        """
        return "<Share %s %s>" % (self.name, self.client)

    def delete(self):
        """ This delete method is overridden because Share objects are
        identified by both name and client.
        """
        self.resource.delete(self.name, self.client)

    def __eq__(self, other):
        """ Implements the equal condition operator for Shares objects.
        """
        return super(Share, self).__eq__(other) and \
               self.client == other.client and self.options == other.options


class FileSystem(NasStorageObject, ExclusiveExceptions):
    """ NasObject class to abstract FileSystem instances of NAS.
    """

    class OnlineException(NasException):
        pass

    class OfflineException(NasException):
        pass

    def __init__(self, resource, name, size, layout, pool, online=True):
        """ The NAS FileSystem objects also has a size, a layout and pool as
        basic attributes.
        """
        super(FileSystem, self).__init__(resource, name, size)
        self.layout = Attr(layout)
        self.pool = Attr(Pool(resource, str(pool))) \
                    if pool is not None else Attr(pool)
        self.online = online

    def is_restore_running(self):
        """ Check if a restore is in progress.
        """
        return self.resource.is_restore_running(self.name)

    def __eq__(self, other):
        """ Implements the equal condition operator for FileSystem objects.
        """
        return super(FileSystem, self).__eq__(other) and \
            self.size == other.size and self.layout == other.layout and \
            self.pool == other.pool


class Disk(NasObject, ExclusiveExceptions):
    """ NasObject class to abstract Disk instances of NAS.
    """


class Pool(NasObject, ExclusiveExceptions):
    """ NasObject class to abstract Pool instances of NAS.
    """


class Cache(NasStorageObject, ExclusiveExceptions):
    """ NasObject class to abstract Cache instances of NAS.
    """

    def __init__(self, resource, name, size, pool=None, used=0,
                 available=0, snapshot_count=None):
        """ The NAS Cache object also has a size and pool as basic attributes.
        """
        super(Cache, self).__init__(resource, name, size)
        self.pool = Attr(Pool(resource, str(pool))) if pool else None
        self.used = Attr(Size("%sM" % used))
        self.available = Attr(Size("%sM" % available))
        self.snapshot_count = Attr(snapshot_count)

    @property
    def used_percentage(self):
        """ This property retrieves the used space in cache as percentage.
        """
        return (self.used.number_in_unit('M') /
                self.size.number_in_unit('M')) * 100

    @property
    def available_percentage(self):
        """ This property retrieves the available space in cache as percentage.
        """
        return (self.available.number_in_unit('M') /
                self.size.number_in_unit('M')) * 100

    def get_related_snapshots(self):
        """ Returns the names of the snapshots related to this cache object.
        """
        return self.resource.get_related_snapshots(self.name)

    def __eq__(self, other):
        """ Implements the equal condition operator for Shares objects.
        """
        return super(Cache, self).__eq__(other) and self.size == other.size \
                                                and self.pool == other.pool


class Snapshot(NasObject, ExclusiveExceptions):
    """ NasObject class to abstract Snapshot instances of a NAS.
    """

    class RestoreException(NasException):
        pass

    class RollsyncRunning(NasException):
        pass

    def __init__(self, resource, name, filesystem, cache=None,
                 snaptype=None, date=None):
        """ The NAS Snapshot object has a name, file system and a cache
         as basic attributes.
        """
        super(Snapshot, self).__init__(resource, name)
        self.filesystem = Attr(filesystem)
        self.cache = Attr(cache) if cache else None
        self.snaptype = Attr(snaptype)
        self.date = Attr(date)

    def __eq__(self, other):
        """ Implements the equal condition operator for Snapshot object.
        """
        return (super(Snapshot, self).__eq__(other) and
                self.filesystem == other.filesystem and
                self.cache == other.cache)

    def delete(self):
        """ This delete method is overridden because Snapshot objects are
        identified by both name and file system.
        """
        self.resource.delete(self.name, self.filesystem)


class NasServer(NasObject, ExclusiveExceptions):
    """ NasObject class to abstract NasServer instances of a NAS.
    """

    def __init__(self, resource, name, pool, homesp):
        """ The NasServer objects also have pool and sp
        as basic attributes.
        """
        super(NasServer, self).__init__(resource, name)
        self.pool = Attr(Pool(resource, str(pool)))
        self.homesp = Attr(homesp)
