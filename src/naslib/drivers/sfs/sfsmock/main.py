##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" Contains the SfsMock class implementation, for mocking the SFS Server
outputs.
"""

from ....nasmock.base import BaseMock
from ..main import Sfs
from .db import SfsMockDb


class SfsMock(Sfs, BaseMock):
    """ This class is quite almost the same as original Sfs, but inherits from
    BaseMock and includes the mock_db_class that contains the database of
    outputs mocked from SFS.
    """
    mock_db_class = SfsMockDb

    retries = 2
    time_between_retries = 1  # second

    def __init__(self, *args, **kwargs):
        """ This constructor just includes a new attribute sfs_user to mock
        the user privileges in SFS. Please refer to SfsMockDb class.
        """
        super(SfsMock, self).__init__(*args, **kwargs)
        self.sfs_user = ""
