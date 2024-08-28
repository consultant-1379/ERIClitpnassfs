##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,W0221,E0712
""" SSH helpers using paramiko library.
"""

import os
import socket

from .log import NasLogger
from .nasexceptions import NasExecutionTimeoutException, NasException
from .paramikopatch import SSHClient as ParamikoSSHClient, SSHException, \
    PatchedTransport, PatchedHostKeys, InvalidHostKeyEntries, AutoAddPolicy, \
    OpenChannelTimeout


CONNECT_TIMEOUT = 5 * 60
KNOWN_HOSTS_PATH = os.path.expanduser('~/.ssh/known_hosts')


class SSHClient(object):
    """ This class implements basic features of paramiko library in order to
    run remote commands.
    """
    logger = NasLogger.instance()

    def __init__(self, host, user, password=None, port=22):
        """ This constructor requires the connection arguments.
        >>> SSHClient("host", "user")
        <SSHClient host 22>
        >>> p = "some_password"
        >>> client = SSHClient("host2", "user2", p, port=24)
        >>> client
        <SSHClient host2 24>
        >>> client.password == p
        True
        >>> client._ssh is None
        True
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self._ssh = None

    def __str__(self):
        """ Retrieves the str informal representation of this object.
        >>> client = SSHClient("host", "user")
        >>> str(client)
        '<SSHClient host 22>'
        """
        return "<SSHClient %s %s>" % (self.host, self.port)

    def __repr__(self):
        """ Retrieves the official representation of this object.
        >>> client = SSHClient("host", "user")
        >>> repr(client)
        '<SSHClient host 22>'
        """
        return self.__str__()

    @classmethod
    def get_remote_host_key(cls, host, port=22, timeout=CONNECT_TIMEOUT):
        """ Retrieves the host key from the server given the host name and the
        port.
        """
        cls.logger.trace.debug('Getting address info for %s:%s' % (host, port))
        addr_info = socket.getaddrinfo(host, port)
        sock_stream_info = next(((i[0], i[4]) for i in addr_info
                                 if i[1] == socket.SOCK_STREAM), None)
        if sock_stream_info is None:
            raise SSHException('No suitable address family for %s' % host)
        cls.logger.trace.debug('Address info retrieved (%s, %s)' %
                               sock_stream_info)
        family, addr = sock_stream_info
        cls.logger.trace.debug('Setting socket for family %s' % family)
        sock = socket.socket(family, socket.SOCK_STREAM)
        if timeout:
            try:
                sock.settimeout(timeout)
            except Exception as err:  # pylint: disable=I0011,W0703
                cls.logger.trace.debug('Error while trying to set socket '
                                       'timeout: %s' % err)
        cls.logger.trace.debug('Trying to connect to the address %s' %
                               str(addr))
        try:
            sock.connect(addr)
        except (socket.timeout, socket.error) as err:
            msg = "Attempt to establish a connection to retrieve the remote " \
                  "host key failed. Error details: %s" % err
            raise NasException(msg)

        t = PatchedTransport(sock)
        cls.logger.trace.debug('Starting client to get the host key')
        t.start_client()
        cls.logger.trace.debug('Getting the host key')
        key = t.get_remote_server_key()
        cls.logger.trace.debug('Closing transport after getting the host key')
        t.close()
        return key

    @classmethod
    def save_host_key(cls, host, key, known_hosts_path=KNOWN_HOSTS_PATH):
        """ Saves a host key in the known_hosts file. The default path for the
        known_hosts file is "~/.ssh/known_hosts".
        """
        cls.logger.trace.debug('Saving host key for "%s" in "%s" file.' %
                               (host, known_hosts_path))
        try:
            host_keys = cls.get_known_hosts_keys()
        except IOError as err:
            if err.errno == os.errno.ENOENT:  # No such file or directory
                cls.logger.trace.info('Known hosts keys are not loaded as the '
                                      '"%s" file does not exist. The file '
                                      'shall be automatically generated in '
                                      'order to save the host key.' %
                                      known_hosts_path)
            else:
                cls.logger.trace.info('Known hosts keys are not loaded: %s. ' %
                                      err)
            host_keys = PatchedHostKeys()

        cls.logger.trace.debug('The current number of entries in "%s" file '
                          'is %s.' % (known_hosts_path, len(host_keys.keys())))
        host_keys.add(host, key.get_name(), key)
        cls.logger.trace.debug('The number of entries in "%s" file after the '
                               'new is added is %s.' % (known_hosts_path,
                                                        len(host_keys.keys())))
        if not os.path.exists(known_hosts_path):
            directory, _ = os.path.split(known_hosts_path)
            if not os.path.exists(directory):
                cls.logger.trace.debug('Directory "%s" does not exist, '
                                       'creating it.' % directory)
                os.makedirs(directory)
        host_keys.save(known_hosts_path)
        cls.logger.trace.debug('Host key for "%s" is now saved in "%s" file.' %
                               (host, known_hosts_path))

    @classmethod
    def get_known_hosts_keys(cls, known_hosts_path=KNOWN_HOSTS_PATH):
        """ Return a PatchedHostKeys object containing all the information
        of the known_hosts file.
        """
        cls.logger.trace.debug('Loading host keys from "%s" file.' %
                               known_hosts_path)
        host_keys = PatchedHostKeys()
        try:
            host_keys.load(known_hosts_path)
        except InvalidHostKeyEntries as err:
            cls._log_bad_known_host_keys(err)
        return host_keys

    @classmethod
    def _log_bad_known_host_keys(cls, error_exception):
        base_error_msg = 'Failed to parse entries in the ' \
           'known_hosts file before trying to establish SSH connection as ' \
           'they seem to be corrupted. Continuing the connection with the ' \
           'valid known_host'
        errors = ', '.join(["(Line: %s, Error: %s)" % (l, e) for e, l
                            in error_exception.exceptions_lines])
        if len(error_exception.exceptions_lines) == 1:
            msg = "%s. The corrupted line is: %s" % (base_error_msg, errors)
        else:
            msg = "%s. The corrupted lines are: %s" % (base_error_msg, errors)
        cls.logger.trace.warn(msg)

    @property
    def ssh(self):
        """ Gets the paramiko SSHClient object connected.
        """
        if self._ssh is not None:
            if not self.is_connected():
                self.logger.trace.debug("connection lost to NAS server, will "
                           "try again now")
                self.connect()
            return self._ssh
        self.connect()
        return self._ssh

    def connect(self):
        """ Builds the paramikopatch.SSHClient (e.g.: paramiko) object, sets
        the system keys, the missing host key (for .ssh/know_host file) and try
        to establish the SSH connection.
        """
        if self._ssh is not None:
            return
        self._ssh = ParamikoSSHClient()
        try:
            self._ssh.load_system_host_keys()
        except InvalidHostKeyEntries as err:
            self._log_bad_known_host_keys(err)
        self._ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.logger.trace.debug("connecting to the NAS server")
        self._ssh.connect(self.host, self.port, self.user, self.password,
                          timeout=CONNECT_TIMEOUT)
        self.logger.trace.debug("connection to the NAS server has been "
                                "established.")

    def is_connected(self):
        """ Checks the SSH connectivity.
        """
        transport = self._ssh.get_transport() if self._ssh else None
        return bool(transport and transport.is_active())

    def run(self, cmd, timeout=None):
        """ Uses paramiko SSHClient object to execute commands remotely and
        retrieves the correspond standard output and standard error.
        """
        self.logger.trace.debug("running (%s)" % cmd)
        timeout_msg = "A timeout of %s seconds occurred after trying to " \
                      "execute the following command remotely through SSH: " \
                      "\"%s\". Error: %s"
        try:
            stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)[1:]
            self.logger.trace.debug("the paramiko exec_command ran "
                                    "successfully (%s)" % cmd)
            out = stdout.readlines()
            self.logger.trace.debug("paramiko stdout.readlines() ran "
                                    "successfully (%s)"
                       % cmd)
            err = stderr.readlines()
            self.logger.trace.debug("paramiko stderr.readlines() ran "
                                    "successfully (%s)" % cmd)
            # IMPORTANT: the exit status must be caught after reading the
            # stdout and stderr, since the timeout exception will be only
            # raised by reading those buffers. Paramiko may hang while
            # executing recv_exit_status before reading the buffers.
            status = stdout.channel.recv_exit_status()
            if status != 0:
                self.logger.trace.debug("paramiko status: %s (%s)" % (status,
                                                                      cmd))
                err = out + err
                out = []
        except socket.timeout as err:
            msg = timeout_msg % (timeout, cmd, str(err))
            self.logger.trace.warn("naslib: socket.timeout: %s" % msg)
            raise NasExecutionTimeoutException(msg)
        except OpenChannelTimeout as err:
            msg = timeout_msg % (timeout, cmd, str(err))
            self.logger.trace.warn("naslib: OpenChannelTimeout: %s" % msg)
            raise NasExecutionTimeoutException(msg)
        self.logger.trace.debug("ran (%s)" % cmd)
        return status, "".join(out), "".join(err)

    def close(self):
        """ Closes the ssh connection properly.
        """
        self.logger.trace.debug("closing connection to the NAS server")
        self._ssh.close()
        self._ssh = None
        self.logger.trace.debug("NAS server connection closed")
