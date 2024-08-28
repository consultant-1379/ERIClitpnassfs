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
MockDbResourceBase to define resources for the Mock Database.
"""

from ..objects import FileSystem, Share, Disk, Pool, Cache, Snapshot
from .basedbresource import MockDbResourceBase

ANY_GENERIC_ERROR = 'any_generic_error'


class BaseMockDbFilesystem(MockDbResourceBase):
    """ Database that mocks the information related to file systems.
    """
    nas_object_class = FileSystem


class BaseMockDbShare(MockDbResourceBase):
    """ Database that mocks the information related to shares.
    """
    nas_object_class = Share


class BaseMockDbDisk(MockDbResourceBase):
    """ Database that mocks the information related to disks.
    """
    nas_object_class = Disk


class BaseMockDbPool(MockDbResourceBase):
    """ Database that mocks the information related to pools.
    """
    nas_object_class = Pool


class BaseMockDbSnapshot(MockDbResourceBase):
    """ Database that mocks the information related to pools.
    """
    nas_object_class = Snapshot


class BaseMockDbCache(MockDbResourceBase):
    """ Database that mocks the information related to caches.
    """
    nas_object_class = Cache
