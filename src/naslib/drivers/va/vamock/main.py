##############################################################################
# COPYRIGHT Ericsson AB 2016
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" Contains the VaMock class implementation, for mocking the VA Server
outputs.
"""

from ...sfs.sfsmock.main import SfsMock
from ..main import Va
from .db import VaMockDb


class VaMock(Va, SfsMock):
    """ Inherit from SfsMock and just include the VA mock_db_class that
    contains the database of outputs mocked from VA.
    """
    mock_db_class = VaMockDb
