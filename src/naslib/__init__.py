##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This package contains the abstraction implementation for NAS servers.
"""

import inspect
import re

from . import drivers
from .base import NasBase
from .nasmock.base import BaseMock
from .nasexceptions import NasDriverDoesNotExist, NasImplementationError, \
                            UnableToDiscoverDriver
from .ssh import SSHClient


SFS_SYSTEM_STATUS_REGEX = re.compile(r"^Status\s+\:\s+\w+")
RHEL_NFS_UNAME_REGEX = re.compile(r"GNU/Linux")


class NasDriversMeta(type):
    """ This metaclass dynamically sets attributes in the NasDrivers class.
    """

    def __new__(mcs, this_name, bases, attr):
        """ It uses inspection to check in the "drivers" module, the classes
        based on NasBase or BaseMock and set those classes as new entry in the
        dicts _drivers. It also sets new attribute with the given driver class
        name.
        """
        attr['_drivers'] = {}
        mocks = []
        for name, member in inspect.getmembers(drivers):
            if name.startswith('__'):
                continue
            if inspect.isclass(member):
                if issubclass(member, NasBase) and member != NasBase and not \
                   issubclass(member, BaseMock):
                    attr[name] = name
                    attr['_drivers'][name] = {'driver': member}
                if issubclass(member, BaseMock):
                    mocks.append(member)
        for mock in mocks:
            mock_bases = mock.__bases__
            mock_bases = [i for i in mock_bases if issubclass(i, NasBase)
                            and i != BaseMock and i != NasBase
                            and not issubclass(i, BaseMock)]

            if mock_bases:
                attr['_drivers'][mock_bases[0].__name__]['mock'] = mock
        return super(NasDriversMeta, mcs).__new__(mcs, this_name, bases, attr)


class NasDrivers(object):
    """ Provides the available drivers and its correspond mocks implemented in
    naslib through the methods get_driver and get_mock methods.
    """

    __metaclass__ = NasDriversMeta

    @classmethod
    def get_drivers(cls):
        """ Returns the cls._drivers dict that is dynamically set by the
        NasDriversMeta metaclass.
        """
        return cls._drivers  # pylint: disable=I0011,E1101

    @classmethod
    def get_driver(cls, ssh):
        """ Uses the verify_discovery method of each driver to see which
        type of NAS server it is connecting to.
        """
        drivs = cls.get_drivers()
        for driver_dict in drivs.values():
            driver = driver_dict['driver'](ssh)
            if driver.verify_discovery():
                return driver

        raise UnableToDiscoverDriver(
                'Unable to discover a driver for the current NAS server')

    @classmethod
    def get_mock(cls, name):
        """ Uses the cls._driver dict to get the driver mock class by the given
        name.
        """
        drivs = cls.get_drivers()
        try:
            return drivs[name]['mock']
        except KeyError:
            raise NasDriverDoesNotExist('The driver "%s" does not have a mock '
                                        'class implemented.' % name)
