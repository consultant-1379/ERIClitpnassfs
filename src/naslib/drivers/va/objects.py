##############################################################################
# COPYRIGHT Ericsson AB 2016
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
from ..sfs.objects import SfsFileSystem
from ..sfs.utils import VxCommands
from ...baseobject import LazyAttr
from ...nasexceptions import NasIncompleteParsedInformation
from ...objects import Pool


class VaFileSystem(SfsFileSystem):

    def __init__(self, resource, name, size, layout, online, pool=None):
        super(VaFileSystem, self).__init__(resource, name, size, layout,
                                            pool, online)
        self.pool = LazyAttr(pool, self.get_pool)

    def get_pool(self):
        """ Retrieves a Pool object related to this file system by parsing
        information from the vxvm commands (vxprint, vxdisk listtag) on Va.
        """
        vx = VxCommands(self.resource.nas)
        try:
            pool = vx.get_pools_disks_from_object(self.name)[1][0]
        except KeyError:
            raise NasIncompleteParsedInformation("The output information "
                "returned from VA was incomplete, having empty values for "
                "the pool name.", self.name)
        return Pool(self.resource, pool)
