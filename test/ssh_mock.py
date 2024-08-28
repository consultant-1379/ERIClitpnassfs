##############################################################################
# COPYRIGHT Ericsson AB 2013
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################


SSH_PORT = 22


class Channel(object):

    def __init__(self, exit_status):
        self.recv_exit_status = lambda : exit_status


class StandardInOutErr(object):

    def __init__(self, lines="", exit_status=0):
        self.readlines = lambda : ["%s\n" % i for i in lines.splitlines()]
        self.read = lambda : lines
        self.channel = Channel(exit_status)


class SSHClient(object):

    """Mock SSH client for unit test.
    """

    def __init__(self, *args, **kwargs):
        super(SSHClient, *args, **kwargs)
        self.exit_status = 0

    def load_system_host_keys(self, filename=None):
        pass

    def load_host_keys(self, filename):
        pass

    def save_host_keys(self, filename):
        pass

    def get_host_keys(self):
        return None

    def set_log_channel(self, name):
        pass

    def set_missing_host_key_policy(self, policy):
        pass

    def connect(self, hostname, port=SSH_PORT, username=None, password=None,
                pkey=None, key_filename=None, timeout=None, allow_agent=True,
                look_for_keys=True, compress=False, sock=None):
        pass

    def close(self):
        pass

    def exec_command(self, *args, **kwargs):
        return StandardInOutErr(exit_status=self.exit_status),\
               StandardInOutErr("line1\nline2", self.exit_status), \
               StandardInOutErr(exit_status=self.exit_status)

    def invoke_shell(self, term='vt100', width=80, height=24, width_pixels=0,
                     height_pixels=0):
        return None

    def open_sftp(self):
        return None

    def get_transport(self):
        return None


class Transport(object):
    def __init__(self, *args):
        pass

    def connect(self, hostkey=None, username='', password=None, pkey=None):
        pass


class SFTPClient(object):
    def __init__(self, *args):
        pass

    def from_transport(cls, t):
        pass
    from_transport = classmethod(from_transport)


class AutoAddPolicy (object):

    """Mock object
    """

    def missing_host_key(self, client, hostname, key):
        pass
