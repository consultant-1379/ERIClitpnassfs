##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the base class for mocking a NasBase.
"""

from abc import ABCMeta, abstractmethod

from ..base import NasBase


class BaseMock(NasBase):
    """ This class is quite almost the same as original NasBase, but just
    replaces the self.ssh SSHClient class as the SshClientMock that will behave
    like a server in terms of output.
    """
    __metaclass__ = ABCMeta

    mock_db_class = None

    def __init__(self, ssh, stash=False, output=None, exception=None):
        """
        This constructor includes more optional arguments such as:
         - stash: used in MockDb for a provisory DB use in a context manager.
         - output: must be a tuple containing:
           1. a compiled regular expression representing the command to caught;
           2. the success output to be retrieved by the given command regex;
           3. the error output to be retrieved by the given command regex;
         - exception: it will be raised when some command is executed.
        """
        self.stash = stash
        self.exception = exception
        self.output = output
        super(BaseMock, self).__init__(ssh)
        self.ssh.exception = exception

    @abstractmethod
    def execute(self, cmd, timeout=None):
        """ Must be implemented. Usually, the subclasses of a BaseMock have
        multiple inheritance and the other class should have this method
        already implemented.
        """
