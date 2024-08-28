    #########################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the Context Manager class implementation
for a generic NFS connection.
"""

import traceback
import sys
import paramiko
import socket

from . import NasDrivers
from .unityxt.main import UnityXT
from .log import NasLogger
from .nasexceptions import NasConnectionException
from .ssh import SSHClient


class NasConnection(object):
    """ This class implements a context manager for a connection to a NFS
    server. The ssh client creates and closes the connection inside the
    "with" statement.
    """

    logger = NasLogger.instance()

    def __init__(self, host, username, password=None, port=22,
            nas_type='veritas'):
        """ The driver_name argument is required, e.g.: NasDrivers.sfs. The
        remaining ones are arguments for the SSH connection.
            host - A string containing the ssh host
            username - A string containing the ssh username
            password - A string containing the ssh password
            port - An integer indicating the ssh port
        """
        self.driver = None
        self.nas_type = nas_type
        if self.nas_type == 'veritas':
            self.ssh = SSHClient(host, username, password, port)
        else:
            self.unityxt = UnityXT(host, username, password)

    @property
    def driver_instance(self):
        """ Retrieves the NFS class by NasDrivers.
        """
        return NasDrivers.get_driver(self.ssh)

    def __enter__(self):
        """ When entering into "with" statement, the NFS driver is
        instantiated according to the NasDrivers and through the connection
        arguments. After that the ssh connection is opened and it returns the
        NFS object instance.
        """
        if self.nas_type == 'veritas':
            try:
                self.ssh.connect()
            except (socket.error, paramiko.BadAuthenticationType,
                    paramiko.BadHostKeyException,
                    paramiko.AuthenticationException):
                exc_type, exc_val, exc_tb = sys.exc_info()
                tb = ''.join(
                    traceback.format_tb(exc_tb)) if exc_tb else ''
                self.logger.trace.debug("%s\n%s: %s" % (tb, exc_type, exc_val))
                raise NasConnectionException(exc_val), None, exc_tb

            return self.driver_instance
        else:
            self.unityxt.login()
            return self.unityxt

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ When exiting from the "with" statement the SSH connection is closed
        and if was because an error, the correspond exception will be raised.
        """
        if self.nas_type == 'veritas':
            self.ssh.close()
        else:
            self.unityxt.logout()
        # XXX: should we treat an exception while trying to close the
        # connection? Maybe pass if it raises an exception, so the plan
        # will not have to be failed since maybe the connection was
        # eventually closed after doing all the stuff, I don't know.
        if exc_type:
            tb = ''.join(traceback.format_tb(exc_tb)) if exc_tb else ''
            if exc_type == socket.error:
                self.logger.trace.debug("%s\n%s: %s" % (tb, exc_type, exc_val))
                raise NasConnectionException(exc_val), None, exc_tb
            else:
                args = exc_val if isinstance(exc_val, tuple) else \
                     ((exc_val,) if isinstance(exc_val, str) else exc_val.args)
                raise exc_type(*args), None, exc_tb
