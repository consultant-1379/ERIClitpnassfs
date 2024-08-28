##############################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the connection classes mocked.
"""

from .. import NasDrivers
from ..connection import NasConnection
from .ssh import SshClientMock


class NasConnectionMock(NasConnection):
    """ Just like the NasConnection but uses a NFS mock class instead for unit
    tests purposes.

    >>> from naslib.nasexceptions import NasException
    >>> import socket
    >>> conn = NasConnectionMock("host", "username",
    ...     driver_name=NasDrivers.Sfs)
    >>> try:
    ...     with conn as sfs:
    ...         raise socket.error("some error")
    ... except Exception, err:
    ...     pass
    ...
    >>> err.__class__.__name__
    'NasConnectionException'
    >>> try:
    ...     conn.__exit__(socket.error, "some error", None)
    ... except Exception, err:
    ...     pass
    ...
    >>> err.__class__.__name__
    'NasConnectionException'
    """

    mock_dbs = {}

    def __init__(self,  host, username, password=None, port=22,
                 stash=False, output=None, mock_connection_failure=False,
                 driver_name=None, nas_type='veritas'):
        """ It just includes the stash attribute for testing porpuses.
        """
        super(NasConnectionMock, self).__init__(
            host,
            username,
            password,
            port,
            nas_type=nas_type
        )

        self.stash = stash
        self.output = output
        self.mock_connection_failure = mock_connection_failure
        self.driver_name = driver_name
        self.ssh = SshClientMock(host, username, password=None, port=22)

    def __enter__(self):
        self.ssh.mock_connection_failure = self.mock_connection_failure
        driver = super(NasConnectionMock, self).__enter__()
        klass = driver.mock_db_class
        key = driver.mock_db_class.__name__
        if key not in self.__class__.mock_dbs:
            mock_db = klass()  # pylint: disable=I0011,E1102
            self.__class__.mock_dbs[key] = mock_db
        if self.stash or (self.__class__.mock_dbs.get(key) and
                          not self.__class__.mock_dbs[key].data):
            mock_db = klass(stash=self.stash)  # pylint: disable=I0011,E1102
            self.ssh.mock_db = mock_db
        else:
            self.ssh.mock_db = self.__class__.mock_dbs[key]
        self.ssh.output = driver.output
        return driver

    @property
    def driver_instance(self):
        """ Retrieves the MOCK class by the NasDrivers helper. The idea is to
        support other drivers in the future.
        """
        klass = NasDrivers.get_mock(self.driver_name)
        instance = klass(self.ssh, stash=self.stash, output=self.output)
        return instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Before exists the context manager, checks the "stash" to remove
        the cache database and replace with the old one.
        """
        if self.stash:
            ssh = self.driver_instance.ssh
            ssh.mock_db.pop_stash()  # pylint: disable=I0011,E1101
        super(NasConnectionMock, self).__exit__(exc_type, exc_val, exc_tb)
