##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
from ..base import NasBase, register_resources
from .resources import FileSystemResource, ShareResource, DiskResource, \
                        PoolResource, CacheResource, SnapshotResource, \
                        NasServerResource
from ..log import NasLogger

from .unityrest import UnityREST


@register_resources(FileSystemResource, ShareResource, DiskResource,
                    PoolResource, CacheResource, SnapshotResource,
                    NasServerResource)
class UnityXT(NasBase):

    # Need for NasBase.__str__ to return a string
    name = 'UnityXT'

    logger = NasLogger.instance().trace

    def __init__(self, host, username, password):
        self.rest = UnityREST(self.logger)
        self.host = host
        self.username = username
        self.password = password

        super(UnityXT, self).__init__(None)

    def execute(self, cmd, timeout=None):
        raise NotImplementedError

    def execute_cmd(self, cmd, timeout=None):
        raise NotImplementedError

    def verify_discovery(self):
        raise NotImplementedError

    def login(self):
        self.logger.debug("UnityXT.login")
        self.rest.login(self.host, self.username, self.password)

    def logout(self):
        self.logger.debug("UnityXT.logout")
        self.rest.request('/api/types/loginSessionInfo/action/logout', 'POST')
