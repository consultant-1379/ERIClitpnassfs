##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the abstract implementation for Symantec FileStore
as the Sfs class is based on NASBase. The corresponding NFS resources classes
are imported to register into the Sfs class.
 """

import re
import time

from ...base import NasBase, register_resources
from ...log import NasLogger
from ...nasexceptions import NasExecCommandException, NasBadUserException, \
                             NasBadPrivilegesException
from .resources import FileSystemResource, ShareResource, DiskResource, \
                        PoolResource, CacheResource, SnapshotResource
from .parsers import SfsAdminShowParser

# Strings that could show up in stderr but don't mean there was an actual error
STDERRS_TO_IGNORE = [re.compile(r'.*Waiting\s+for\s+other\s+command\s+\(.*\)'
                     r'\s+to\s+complete.*'), re.compile(r'^\.+$'),
                     re.compile(r'.*lock\.lock: No such file or directory.*')]


@register_resources(FileSystemResource, ShareResource, DiskResource,
                    PoolResource, CacheResource, SnapshotResource)
class Sfs(NasBase):
    """ Nas driver class for managing Symantec File Store nfs services
    """

    name = 'SFS'
    clish_base_cmd = "LANG=C /opt/VRTSnasgw/clish/bin/clish -u %s -c '%s'"
    string_is_bash_test = "is_bash_test"
    is_bash_cmd = "echo %s" % string_is_bash_test
    check_privileges_cmd = "admin show %s"
    master_privileges = 'Master'
    error_regex = re.compile(r'SFS\s\w+\sERROR')
    info_regex = re.compile(r'SFS\s\w+\sINFO')
    session_disconnect_regex = re.compile(r'Found\s+CVM\s+master\s+not\s+in\s+'
        r'current\s+node,\s+switching\s+the\s+console,\s+current\s+session\s+'
        r'will\s+get\s+disconnected')
    discovery_path = '/opt/VRTSnasgw/clish/bin/clish'
    retries = 3
    time_between_retries = 10  # seconds

    logger = NasLogger.instance()

    def __init__(self, *args, **kwargs):
        """ Just includes a new cache attribute (_is_bash) to this SFS object.
        """
        super(Sfs, self).__init__(*args, **kwargs)
        self.sfs_user = "master"
        self._is_bash = None
        self._is_master = None

    @property
    def is_bash(self):
        """ Checks through a single bash command whether the user is inside
        a bash console.
        """
        if self._is_bash is not None and not self.ssh.is_connected():
            # resets the cache in case the connection is dropped
            self._is_bash = None
        if self._is_bash is None:
            out = self.ssh.run(self.is_bash_cmd)[1]
            self._is_bash = self.string_is_bash_test == out.strip()
        return self._is_bash

    @property
    def is_master(self):
        """ Checks the privileges of the current user.
        """
        if self.sfs_user == 'master':
            return True
        if self._is_master is not None and not self.ssh.is_connected():
            # resets the cache in case the connection is dropped
            self._is_master = None
        if self._is_master is None:
            cmd = self.check_privileges_cmd % self.sfs_user
            out = self.ssh.run(cmd)[1]
            parser = SfsAdminShowParser(out)
            data = parser.parse()
            try:
                privileges = data['Privileges']
            except KeyError:
                self.logger.trace.warning('Cannot parse the privileges '
                    'information related to the "%s" user. The output of the '
                    'command "%s" is:\n%s' % (self.ssh.user, cmd, out))
                self._is_master = False
                return self._is_master
            self._is_master = privileges == self.master_privileges
        return self._is_master

    def verify_discovery(self):
        """ Checks if discovery path for given Veritas NAS is present on
        Veritas NAS box and based on the clish location set the nassfs driver
        """
        test = "/usr/bin/test -f "
        status = self.ssh.run(test + self.discovery_path)[0]
        return status == 0

    def execute(self, cmd, timeout=None,  # pylint: disable=I0011,W0221
                env=None):  # pylint: disable=I0011,W0221
        """ Overrides the the base execution since Sfs doesn't provide properly
        a stderr nor a status code.
        """

        def _execute(num_retries=0):
            self.debug('Running command: "%s"' % cmd)
            _, out, err = self._run(cmd, timeout=timeout, env=env)
            self.debug('Ran command: "%s", out: "%s", err: "%s"' % (cmd, out,
                                                                    err))
            if (err and not any(r.search(err) for r in STDERRS_TO_IGNORE)) or\
            self.error_regex.search(out):
                new_out = self._strip_lines(out) + self._strip_lines(err)
                raise NasExecCommandException('\n'.join(new_out))
            if self.info_regex.search(out):
                self.warn("Info message got from %s: %s" % (self.name, out))

                if self.session_disconnect_regex.search(out):
                    # When SFS provides this INFO message, it's usually because
                    # a connection issue. It might be intermittent and that's
                    # why it will retry to execute for "self.retries" times
                    # after "self.time_between_retries" seconds.
                    num_retries += 1
                    if num_retries > self.retries:
                        raise NasExecCommandException(
                            "Failed after %s retries. %s output: %s" %
                            (num_retries, self.name, out))
                    time.sleep(self.time_between_retries)
                    s = {1: 'st', 2: 'nd', 3: 'rd'}
                    time_retry = "%s%s" % (num_retries,
                                           s.get(num_retries, 'th'))
                    self.debug('Retrying for the %s time to run the following '
                               'command: %s' % (time_retry, cmd))
                    return _execute(num_retries)
            return out

        out = _execute()
        return self._strip_lines(out)

    def _run(self, cmd, timeout=None, env=None):
        """ Runs a SFS command through SSH connection. It checks first where
        the user is get into (bash or SFS console) after connecting, before
        running any command. We assume that, if it's not bash console, it's
        SFS console. This Sfs wrapper should only allow users to connect
        through bash console.
        """
        if not self.is_bash:
            # raise exception so we can avoid unexpected errors forward.
            raise NasBadUserException('The user "%s" should have their '
                       'default login shell set to /bin/bash.' % self.ssh.user)
        if not self.is_master:
            raise NasBadPrivilegesException('The "%s" user should have '
                                        '"Master" privileges.' % self.sfs_user)
        clish_cmd = self.clish_base_cmd % (self.sfs_user, cmd)
        if env is not None:
            environment_vars = ' '.join(['%s=%s' % t for t in env.items()])
            clish_cmd = "%s %s" % (environment_vars, clish_cmd)

        return self.ssh.run(clish_cmd, timeout=timeout)
