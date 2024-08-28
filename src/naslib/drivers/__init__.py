##############################################################################
# COPYRIGHT Ericsson AB 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This is the main module for all the drivers of naslib.
New drivers implemented must be imported in this module, including the
correspond "mock class", to be registered and visible by the naslib.NasDrivers.
"""

# Drivers
from .va.main import Va
from .sfs.main import Sfs
from .va74.main import Va74

# Mocks
from .sfs.sfsmock.main import SfsMock
from .va.vamock.main import VaMock
