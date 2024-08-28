##############################################################################
# COPYRIGHT Ericsson AB 2016
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the implementation of the VaMockDb class for specific
behavior in VA Server.
"""

from .dbresources import VaMockDbFilesystem, VaMockDbShare, VaMockDbDisk, \
                       VaMockDbCache, VaMockDbPool, VaMockDbSnapshot
from ...sfs.sfsmock.db import SfsMockDb
from ....nasmock.db import register_db_resources


@register_db_resources(VaMockDbFilesystem, VaMockDbShare, VaMockDbDisk,
                       VaMockDbCache, VaMockDbPool, VaMockDbSnapshot)
class VaMockDb(SfsMockDb):
    def error_message(self, resource, err):
        """ Overrides the base method to provide an error message in the VA
        specific format.
        """
        super(VaMockDb, self).error_message(resource, err)
        return "ACCESS %s ERROR %s" % (resource.name, str(err))
