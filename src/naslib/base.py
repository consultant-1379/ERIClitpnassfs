##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" Base module containing the NasBase abstract class.
"""

from abc import ABCMeta, abstractmethod

from .baseresources import FileSystemResourceBase, ShareResourceBase, \
    DiskResourceBase, PoolResourceBase, CacheResourceBase, ResourceBase, \
    SnapshotResourceBase, NasServerResourceBase
from .log import NasLogger
from .nasexceptions import NasImplementationError


def register_resources(*args):
    """ Class decorator that dynamically sets the 7 resources of an
    NFS server as a list in the __resources__ attribute into NasBase class.

    The 7 resources must be a based on:
     - FileSystemResourceBase;
     - ShareResourceBase;
     - DiskResourceBase;
     - PoolResourceBase;
     - CacheResourceBase;
     - SnapshotResourceBase;
     - NasServerResourceBase.

    Wrong type resource should raise an NasImplementationError.

    >>> class FakeRes(object):
    ...     pass
    ...
    >>> try:
    ...     @register_resources(FakeRes, FakeRes, FakeRes, FakeRes,
    ...                         FakeRes, FakeRes)
    ...     class MyNas(NasBase):
    ...         pass
    ... except Exception, err:
    ...     pass
    ...
    >>> isinstance(err, NasImplementationError)
    True
    >>> str(err)
    'Resources classes should be ResourceBase based.'
    >>> try:
    ...     @register_resources(FakeRes, FakeRes, FakeRes, FakeRes,
    ...                         FakeRes, FakeRes)
    ...     class MyNas(object):
    ...         pass
    ... except Exception, err:
    ...     pass
    ...
    >>> isinstance(err, NasImplementationError)
    True
    >>> str(err)
    'The class MyNas must be a sub class of NasBase'
    """
    def register(klass):
        if globals().get('NasBase') and not issubclass(klass, NasBase):
            name = klass.__name__
            msg = "The class %s must be a sub class of NasBase" % name
            raise NasImplementationError(msg)
        if not all([issubclass(i, ResourceBase) for i in args]):
            msg = "Resources classes should be ResourceBase based."
            raise NasImplementationError(msg)
        setattr(klass, '__resources__', args)
        return klass
    return register


@register_resources(FileSystemResourceBase, ShareResourceBase,
                    DiskResourceBase, PoolResourceBase, CacheResourceBase,
                    SnapshotResourceBase, NasServerResourceBase)
class NasBase(object):
    """ Abstract base class that contain methods for NAS server management.
    This class provides a mechanism to execute SSH commands on a NAS server.
    It also depends on those ResourceBase resources to be necessarily
    registered:
     - FileSystem resource;
     - ShareResource;
     - DiskResource;
     - PoolResource;
     - CacheResource;
     - SnapshotResource;
     - NasServerResource.

    Each resource must be a subclass of resources.ResourceBase that provides
    this basic methods : list, get, exists, create and delete. For further
    information look at the resources.ResourceBase documentation.
    """
    __metaclass__ = ABCMeta
    name = None
    logger = NasLogger.instance()

    def __init__(self, ssh):
        """ Constructor of the NasBase class. It properly instantiates each
        NAS resource previously defined on NasBase.__resources__ by
        @register_resources class decorator.
        """
        for ResourceClass in getattr(self, '__resources__'):
            setattr(self, ResourceClass._base_attr_name,
                    ResourceClass(self))
        self.output_history = []
        self.ssh = ssh
        #self._set_ssh(host, username, password, port)

    def __str__(self):
        """ Returns the name of this object.
        """
        return self.name

    def __repr__(self):
        """ Returns the representative string of this object.
        """
        return "<%s>" % self.__class__.__name__

    def _strip_lines(self, out):
        """ Helper that splits the lines of a generic output string removing
        the empty ones.
        """
        return [i for i in out.splitlines() if i.strip()]

    def debug(self, msg):
        self.logger.trace.debug("%s: %s" % (self.__class__.__name__, msg))

    def warn(self, msg):
        self.logger.trace.warn("%s: %s" % (self.__class__.__name__, msg))

    @abstractmethod
    def execute(self, cmd, timeout=None):
        """ Basic method to properly execute NFS commands.
        """

    @abstractmethod
    def verify_discovery(self):
        """ Returns True if the file of self.discovery_path of a
        driver exists. Used to distinguish what type of NAS we are
        connected SFS, ISA etc..
        """
