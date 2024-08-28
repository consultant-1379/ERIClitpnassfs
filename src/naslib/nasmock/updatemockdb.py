##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the update_mock_db function for bash command call
"python -m naslib.nasmock.updatemockdb". It gets information from
NAS server and populates the "resources.mock.json" file to be used as the
database for this nasmock.
"""

import sys
from optparse import OptionParser

from .. import NasDrivers
from ..nasexceptions import NasDriverDoesNotExist
from .db import MockDb


METAVAR = "<USER>@<SERVER>:<PORT>"


def _get_system_argument(args):
    """ Get system arguments.
    >>> from optparse import Values
    >>> p, v = _get_system_argument(['--host=user@host:22', '--password=pass'])
    >>> isinstance(p, OptionParser)
    True
    >>> isinstance(v, Values)
    True
    """
    parser = OptionParser()
    parser.usage = "python -m naslib.nasmock.updatemockdb --host=? " \
                   "--password=? --driver=? (--resource=? optional)"
    parser.description = "Updates the %s DB file using data from a " \
                         "given NAS server." % MockDb._resources_db_filename
    parser.add_option("--host", dest="host",
                      help="Must contains a user, a server host or IP address "
                           "and the port is optional. E.g.: user@server:22",
                      metavar=METAVAR)
    parser.add_option("--password", dest="password",
                      help="Password for the given user.")
    parser.add_option("--driver", dest="driver",
                      help="Give a specific driver name (e.g: Sfs).")
    parser.add_option("--resource", dest="resource",
                      help="Give a specific resource name.")
    return parser, parser.parse_args(args)[0]


def msg(m):
    print
    print m
    print


def update_mock_db(args, mock_update=None):
    """ Logs into a NAS server and gets the information of the basic NAS
    resources to store it as the base db for the BaseMock.
    >>> update_mock_db([])
    Usage: python -m naslib.nasmock.updatemockdb --host=? --password=? \
--driver=? (--resource=? optional)
    <BLANKLINE>
    Updates the resources.mock.json DB file using data from a given NAS server.
    <BLANKLINE>
    Options:
      -h, --help            show this help message and exit
      --host=<USER>@<SERVER>:<PORT>
                            Must contains a user, a server host or IP address \
and
                            the port is optional. E.g.: user@server:22
      --password=PASSWORD   Password for the given user.
      --driver=DRIVER       Give a specific driver name (e.g: Sfs).
      --resource=RESOURCE   Give a specific resource name.
    >>> update_mock_db(['--host=foo', '--driver=some'])
    <BLANKLINE>
    The password options must be provided
    <BLANKLINE>
    >>> update_mock_db(['--host=foo', '--driver=some', '--password=pass'])
    <BLANKLINE>
    some is an invalid driver
    <BLANKLINE>
    >>> update_mock_db(['--host=foo', '--driver=Sfs', '--password=pass'])
    <BLANKLINE>
    The host argument must be in the following format: <USER>@<SERVER>:<PORT>
    <BLANKLINE>
    >>> from naslib.drivers.sfs.sfsmock.db import SfsMockDb
    >>> from naslib.drivers.sfs.sfsmock.main import SfsMock
    >>> from .ssh import SshClientMock
    >>> SfsMockDb.ssh_client = SshClientMock
    >>> class FSfsMock(SfsMock):
    ...     mock_db_class = SfsMockDb
    ...
    >>> update_mock_db(['--host=user@host', '--driver=Sfs', '--password=pass',
    ...                 '--resource=cache'], mock_update=FSfsMock)
    >>>
    """
    parser, ops = _get_system_argument(args)
    if ops.host and ops.driver:
        if not ops.password:
            msg("The password options must be provided")
            return
        try:
            mock_class = mock_update or NasDrivers.get_mock(ops.driver)
        except NasDriverDoesNotExist:
            msg('%s is an invalid driver' % ops.driver)
            return
        try:
            user, server = ops.host.split("@")
        except ValueError:
            msg("The host argument must be in the following format: %s" %
                METAVAR)
            return
        try:
            host, port = server.split(":")
        except ValueError:
            port = 22
            host = server
        mock_class.mock_db_class.update_mock_db_data(host, user, ops.password,
                                    int(port), ops.resource, bool(mock_update))
    else:
        parser.print_help()

update_mock_db(  # pylint: disable=I0011,W0106
   sys.argv) if __name__ == '__main__' else None  # pylint: disable=I0011,W0106
