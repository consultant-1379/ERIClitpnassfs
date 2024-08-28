##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the documentation of SshClientMock, that uses a MockDb
instance as the provider for the data coming from a NAS server.
Basically, the SshClientMock overrides the "run" method to instead of executing
a command remotely through SSH, uses the MockDb instance to get the information
given the same command. MockDb provides the mock information stored in a JSON
file, please refer to MockDb documentation for more details.
"""

import socket

from ..ssh import SSHClient
from .mockexceptions import MockException


class SshClientMock(SSHClient):
    """ This class is just a mock implementation of ssh.SSHClient to have the
    behavior like the outputs retrieved by a real server. For this it uses
    the MockDb.
    """

    def __init__(self, host, username, password="", port=22, mock_db=None,
                 output=None, exception=None):
        """ Uses generic args and kwargs just be compatible as the original
        ssh.SSHClient class.
        """
        super(SshClientMock, self).__init__(host, username, password, port)
        # if mock_db is None:
        #     raise MockException('The mock_db argument must be provided.')
        self.mock_db = mock_db
        self.mock_connection_failure = False
        self._is_connected = True
        self.exception = exception
        self.output = output
        self.cmd_regex = None
        self._output = None
        self.error = None

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, output):
        # output must be a tuple of 3 elements. It's used to force outputs.
        if output is not None:
            err_msg = 'output argument must be a tuple of 3 values ' \
                      'containing: (regex, output_string, err_output_string)'
            if not isinstance(output, tuple):
                raise MockException(err_msg)
            if len(output) != 3:
                raise MockException(err_msg)
        else:
            output = (None, None, None)
        regex, out, err = output  # pylint: disable=I0011,W0106,W0633
        self.cmd_regex = regex
        self._output = out
        self.error = err

    def get_resource_action_kwargs_by_command(self, cmd):
        """ Gets the db resource, the action (list, insert, delete) and the
        keywords according to a particular command. Example:
        Given a command like: "nfs share add rw some_share 1.1.1.1" it should
        returns: (NasMockDbShare instance,
                  "insert",
                  {'name': 'some_share', 'host': '1.1.1.1', 'options': 'rw'})
        """
        cmd = self.mock_db.prepare_command(cmd)
        for resource in self.mock_db.resources.list():
            for action, regex in resource.regexes.items():
                if regex is None:
                    continue
                match = regex.match(cmd)
                if not match:
                    continue
                return resource, action, match.groupdict()
        raise MockException("Invalid command '%s'" % cmd)

    def run(self, cmd, timeout=None):
        """ Simulates a command execution through SSH retrieving data from the
        MockDb.
        """
        if self.exception is not None:
            exception = self.exception
            self.exception = None
            raise exception  # pylint: disable=I0011,E0702

        # forcing output mocking feature
        if self.output is not None and self.cmd_regex.search(cmd):
            return 0, self.output, self.error

        _, out, err = self.mock_db.generic_mock_output(cmd)
        if out or err:
            return 0, out, err

        resource, action, kw = self.get_resource_action_kwargs_by_command(cmd)
        try:
            result = getattr(resource, action)(**kw)
        except MockException, err:
            return 0, self.mock_db.error_message(resource, err), ""
        return 0, result or "", ""

    def connect(self):
        """ Mocks the connect method of ssh.SSHClient.
        """
        if self.mock_connection_failure:
            # just forces connection failure, please refer to the
            # connection.NasConnectionMockFailure class as well.
            raise socket.error('Connection failed')
        self._is_connected = True

    def is_connected(self):
        """ Mocks the connection is always alive.
        """
        return self._is_connected

    def close(self):
        """ Mocks the close connection method of ssh.SSHClient.
        """
