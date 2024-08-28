##############################################################################
# COPYRIGHT Ericsson AB 2015
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,W0221
"""
Patching of Paramiko was initially done to fix timeout issues present in
Paramiko 1.7.5.
These issues are fixed in version 2.1.1 but with small deviations in solution,
for example open_channel in PatchedTransport raises OpenChannelTimeout
exception instead of SSHException which is raised in paramiko Transport class.
These deviations have been kept.
The PatchedHostkeys class has also been patched to notify about bad entries in
the known_hosts file and to allow multiple entries for the same host name
and key type
"""

import threading
import getpass
import time
import paramiko
import socket

from paramiko.channel import Channel
from paramiko.message import Message
from paramiko.common import cMSG_CHANNEL_OPEN
from paramiko.resource import ResourceManager
from paramiko.transport import Transport
from paramiko.ssh_exception import SSHException
from paramiko.hostkeys import HostKeys, HostKeyEntry
from paramiko.util import retry_on_signal, constant_time_bytes_eq
from paramiko.config import SSH_PORT
from errno import ECONNREFUSED, EHOSTUNREACH
from paramiko.ssh_exception import NoValidConnectionsError
from paramiko.py3compat import string_types
from paramiko import AutoAddPolicy  # pylint: disable=I0011,W0611
try:
    from collections import MutableMapping
except ImportError:
    # noinspection PyUnresolvedReferences
    from UserDict import DictMixin as MutableMapping


class OpenChannelTimeout(SSHException):
    """ This exception is used in the PatchedTransport.open_channel method, to
    raise a specific exception in case of lack of connection while opening a
    channel. This exception will be properly propagated to the "run" method of
    the ssh.SSHClient class.
    """
    pass


class PatchedTransport(Transport):
    def open_channel(self, kind, dest_addr=None, src_addr=None,
                     window_size=None, max_packet_size=None,
                     timeout=None):
        """ This method is overridden to raise OpenChannelTimeout Exception
            instead of SSHException if there is a timeout due to lack of
            connection
            Read the comments below in the code to check which changes were
            made comparing to the original code.
        """
        if not self.active:
            raise SSHException('SSH session not active')

        timeout = 3600 if timeout is None else timeout
        self.lock.acquire()
        try:
            window_size = self._sanitize_window_size(window_size)
            max_packet_size = self._sanitize_packet_size(max_packet_size)
            chanid = self._next_channel()
            m = Message()
            m.add_byte(cMSG_CHANNEL_OPEN)
            m.add_string(kind)
            m.add_int(chanid)
            m.add_int(window_size)
            m.add_int(max_packet_size)
            if (kind == 'forwarded-tcpip') or (kind == 'direct-tcpip'):
                m.add_string(dest_addr[0])
                m.add_int(dest_addr[1])
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            elif kind == 'x11':
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            chan = Channel(chanid)
            self._channels.put(chanid, chan)
            self.channel_events[chanid] = event = threading.Event()
            self.channels_seen[chanid] = True
            chan._set_transport(self)
            chan._set_window(window_size, max_packet_size)
        finally:
            self.lock.release()
        self._send_user_message(m)
        start_ts = time.time()
        while True:
            event.wait(0.1)
            if not self.active:
                e = self.get_exception()
                if e is None:
                    e = SSHException('Unable to open channel.')
                raise e
            if event.is_set():
                break
            elif start_ts + timeout < time.time():
                #patch raise OpenChannelTimeout instead of SSHException
                raise OpenChannelTimeout('Channel connection timed out.')
                #end patch

        chan = self._channels.get(chanid)
        if chan is not None:
            return chan
        e = self.get_exception()
        if e is None:
            e = SSHException('Unable to open channel.')
        raise e


class InvalidHostKeyEntries(Exception):

    def __init__(self, exceptions_lines):
        super(InvalidHostKeyEntries, self).__init__(exceptions_lines)
        self.exceptions_lines = exceptions_lines
        self.args = (exceptions_lines,)


class PatchedHostKeys(HostKeys):

    def add(self, hostname, keytype, key):
        """
        **This method is overridden from paramiko's original.**

        NOTE: the old original code replaces any existing entry for a pair
        C{(hostname, keytype)}. The change includes an extra condition
        "and e.key.get_base64() == key.get_base64()" so the entry is considered
        already in the self._entries only if everything are equal
        (hostname, the key type and the key itself). In this case, no replace
        is done and it allows to have multiple different "keys" for the same
        pair C{(hostname, keytype)}.

        Add a host key entry to the table.

        @param hostname: the hostname (or IP) to add
        @type hostname: str
        @param keytype: key type (C{"ssh-rsa"} or C{"ssh-dss"})
        @type keytype: str
        @param key: the key to add
        @type key: L{PKey}
        """
        for e in self._entries:
            if (hostname in e.hostnames) and (e.key.get_name() == keytype)\
                and e.key.get_base64() == key.get_base64():
                # key already in self._entries, so just return
                return
        self._entries.append(HostKeyEntry([hostname], key))

    def load(self, filename):
        """
        **This method is overridden from paramiko's original.**

        Read a file of known SSH host keys, in the format used by openssh.
        This type of file unfortunately doesn't exist on Windows, but on
        posix, it will usually be stored in
        C{os.path.expanduser("~/.ssh/known_hosts")}.

        If this method is called multiple times, the host keys are merged,
        not cleared.  So multiple calls to C{load} will just call L{add},
        replacing any existing entries and adding new ones.

        @param filename: name of the file to read host keys from
        @type filename: str

        @raise IOError: if there was an error reading the file
        """
        bad_entries = []
        with open(filename, 'r') as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if (len(line) == 0) or (line[0] == '#'):
                    continue
                # PATCH: collects the bad entries
                try:
                    e = HostKeyEntry.from_line(line, lineno)
                except (TypeError, ValueError, SSHException) as err:
                    bad_entries.append((err, lineno))
                    continue
                # END PATCH.
                if e is not None:
                    _hostnames = e.hostnames
                    for h in _hostnames:
                        if self.check(h, e.key):
                            e.hostnames.remove(h)
                    if len(e.hostnames):
                        self._entries.append(e)

        # PATCH: raises the exception with the bad entries
        if bad_entries:
            raise InvalidHostKeyEntries(bad_entries)
        # END PATCH.

    def lookup(self, hostname):
        """
        **This method is overridden from paramiko's original.**

        NOTE: the change is to allow duplicate entries in the known_hosts file
        for the same hostname but different base64 key. It should return a
        SubDict instance as the following structure example:

        #>>> host_keys.lookup('1.1.1.1')
        {'rsa': [HostKeyEntry1(), HostKeyEntry2()],
         'dsa': [HostKeyEntry1()]}

        The original lookup method from paramiko returns the same structure a
        bit different though. Instead of values as a list of HostKeyEntry, they
        actually are just the HostKeyEntry itself, meaning that it doesn't
        allow repetition.

        -----------------------------------------------------------------------
                     See below original docstring from paramiko


        Find a hostkey entry for a given hostname or IP.  If no entry is found,
        C{None} is returned.  Otherwise a dictionary of keytype to key is
        returned. The keytype will be either C{"ssh-rsa"} or C{"ssh-dss"}.

        @param hostname: the hostname (or IP) to lookup
        @type hostname: str
        @return: keys associated with this host (or C{None})
        @rtype: dict(str, L{PKey})
        """

        class SubDict(MutableMapping):
            def __init__(self, hostname, entries, hostkeys):
                self._hostname = hostname
                self._entries = entries
                self._hostkeys = hostkeys

            def __getitem__(self, key):
                """ Return a list of HostKeyEntry for the same key type
                (argument "key": rsa, dsa etc).
                """
                # PATCH:
                host_keys = []
                for e in self._entries:
                    if e.key.get_name() == key:
                        host_keys.append(e.key)
                if host_keys:
                    return host_keys
                # END PATCH.
                raise KeyError(key)

            def __iter__(self):
                for k in self.keys():
                    yield k

            def __len__(self):
                return len(self.keys())

            def __delitem__(self, key):
                # PATCH:
                entry_removed = False
                for e in list(self._entries):
                    if e.key.get_name() == key:
                        self._entries.remove(e)
                        entry_removed = True
                if not entry_removed:
                    raise KeyError(key)
                # END PATCH.

            def __setitem__(self, _, vals):
                """ The argument _ is supposed to be the "dict key", but
                instead is not going to be used here as the "dict keys" will be
                looked up through the self._entries list of HostKeyEntry.
                """
                # PATCH:
                vals = vals if isinstance(vals, list) else [vals]
                # always add new ones as it now accepts duplicate keys for the
                # same hostname
                base64_pairs = [(e.key.get_name(), e.key.get_base64())
                                for e in self._entries]
                for val in vals:
                    if (val.get_name(), val.get_base64()) in base64_pairs:
                        # to avoid real duplications like same hostname, same
                        # key type and same base64 key.
                        continue
                    # add a new one
                    e = HostKeyEntry([hostname], val)
                    self._entries.append(e)
                    self._hostkeys._entries.append(e)
                # END PATCH.

            def keys(self):
                """ This method is also changed to do a casting of "set()" to
                avoid duplications in the list as it is now possible to have
                duplicate keys for the same hostname.
                """
                return list(set([e.key.get_name() for e in self._entries
                                 if e.key is not None]))

        entries = []
        for e in self._entries:
            for h in e.hostnames:
                if h.startswith('|1|') and not hostname.startswith('|1|')\
                        and constant_time_bytes_eq(
                        self.hash_host(hostname, h), h) or h == hostname:
                    entries.append(e)
        if len(entries) == 0:
            return None
        return SubDict(hostname, entries, self)

    def check(self, hostname, key):
        """
        **This method is overridden from paramiko's original.**

        Return True if the given key is associated with the given hostname
        in this dictionary.

        :param str hostname: hostname (or IP) of the SSH server
        :param .PKey key: the key to check
        :return:
            ``True`` if the key is associated with the hostname; else ``False``
        """
        k = self.lookup(hostname)
        if k is None:
            return False
        # PATCH:
        host_keys = k.get(key.get_name(), None)
        if not host_keys:
            return False
        return any([k.asbytes() == key.asbytes() for k in host_keys])
        # END PATCH.


class PatchedBadHostKeyException (SSHException):
    """
    The host key given by the SSH server did not match what we were expecting.

    @ivar hostname: the hostname of the SSH server
    @type hostname: str
    @ivar key: the host key presented by the server
    @type key: L{PKey}
    @ivar expected_key: the host key expected
    @type expected_key: L{PKey}

    @since: 1.6
    """
    def __init__(self, hostname, got_key, expected_keys):
        SSHException.__init__(self, 'Host key for server %s does not match!' %
                              hostname)
        self.hostname = hostname
        self.key = got_key
        self.expected_keys = expected_keys


class SSHClient(paramiko.SSHClient):
    """ This class is just to override the exec_command method of 1.7.5 version
    of paramiko that doesn't have the timeout argument. The exec_command method
    has the same implementation as the 1.12.0 version.
    """

    def __init__(self, *args, **kwargs):
        """ This method is overridden to sets the _system_host_keys and the
        _host_keys members with the PatchedHostKeys class created above.
        """
        super(SSHClient, self).__init__(*args, **kwargs)
        self._system_host_keys = PatchedHostKeys()
        self._host_keys = PatchedHostKeys()

    def exec_command(self, command, bufsize=-1, timeout=None, get_pty=False,
                     environment=None,):
        """ This method is overridden to check the transport instance exists
            and raise an exception if not

        NOTE: read the comments below in the code to check which changes were
        made comparing to the original code.
        """
        # PATCH: just an improvement to check whether the transport exists
        # or not and raise an exception afterwards.
        if not self._transport:
            raise SSHException('Unable to open session, the connection is no '
                               'longer active.')
        # END PATCH.

        chan = self._transport.open_session(timeout=timeout)
        if get_pty:
            chan.get_pty()
        chan.settimeout(timeout)
        if environment:
            chan.update_environment(environment)
        chan.exec_command(command)
        stdin = chan.makefile('wb', bufsize)
        stdout = chan.makefile('r', bufsize)
        stderr = chan.makefile_stderr('r', bufsize)
        return stdin, stdout, stderr

    def connect(self, hostname, port=SSH_PORT, username=None, password=None,
                pkey=None, key_filename=None, timeout=None, allow_agent=True,
                look_for_keys=True, compress=False, sock=None, gss_auth=False,
                gss_kex=False, gss_deleg_creds=True, gss_host=None,
                banner_timeout=None):

        if not sock:
            errors = {}
            # Try multiple possible address families (e.g. IPv4 vs IPv6)
            to_try = list(self._families_and_addresses(hostname, port))
            for af, addr in to_try:
                try:
                    sock = socket.socket(af, socket.SOCK_STREAM)
                    if timeout is not None:
                        try:
                            sock.settimeout(timeout)
                        except:  # pylint: disable=I0011,W0702
                            pass
                    retry_on_signal(lambda: sock.connect(addr))
                    # Break out of the loop on success
                    break
                except socket.error as e:
                    # Raise anything that isn't a straight up connection error
                    # (such as a resolution error)
                    if e.errno not in (ECONNREFUSED, EHOSTUNREACH):
                        raise
                    # Capture anything else so we know how the run looks once
                    # iteration is complete. Retain info about which attempt
                    # this was.
                    errors[addr] = e

            # Make sure we explode usefully if no address family attempts
            # succeeded. We've no way of knowing which error is the "right"
            # one, so we construct a hybrid exception containing all the real
            # ones, of a subclass that client code should still be watching for
            # (socket.error)
            if len(errors) == len(to_try):
                raise NoValidConnectionsError(errors)  # pylint: disable=W0710

        t = self._transport = PatchedTransport(sock, gss_kex=gss_kex,
                                        gss_deleg_creds=gss_deleg_creds)
        t.use_compression(compress=compress)
        if gss_kex and gss_host is None:
            t.set_gss_host(hostname)
        elif gss_kex and gss_host is not None:
            t.set_gss_host(gss_host)
        else:
            pass
        if self._log_channel is not None:
            t.set_log_channel(self._log_channel)
        if banner_timeout is not None:
            t.banner_timeout = banner_timeout
        t.start_client(timeout=timeout)
        ResourceManager.register(self, t)  # pylint: disable=I0011,E1120

        server_key = t.get_remote_server_key()
        keytype = server_key.get_name()

        if port == SSH_PORT:
            server_hostkey_name = hostname
        else:
            server_hostkey_name = "[%s]:%d" % (hostname, port)

        # If GSS-API Key Exchange is performed we are not required to check the
        # host key, because the host is authenticated via GSS-API / SSPI as
        # well as our client.
        if not self._transport.use_gss_kex:
            # PATCH:
            our_server_keys = self._system_host_keys.get(server_hostkey_name,
                                                         {}).get(keytype, [])
            if not our_server_keys:
                our_server_keys = self._host_keys.get(server_hostkey_name,
                                                      {}).get(keytype, [])
            if not our_server_keys:
                # will raise exception if the key is rejected; let
                # that fall out
                self._policy.missing_host_key(self, server_hostkey_name,
                                              server_key)
                # if the callback returns, assume the key is ok
                our_server_keys = [server_key]

            if server_key not in our_server_keys:
                raise PatchedBadHostKeyException(hostname, server_key,
                                                 our_server_keys)
            # END PATCH

        if username is None:
            username = getpass.getuser()

        if key_filename is None:
            key_filenames = []
        elif isinstance(key_filename, string_types):
            key_filenames = [key_filename]
        else:
            key_filenames = key_filename
        if gss_host is None:
            gss_host = hostname
        self._auth(username, password, pkey, key_filenames, allow_agent,
                   look_for_keys, gss_auth, gss_kex, gss_deleg_creds, gss_host)
