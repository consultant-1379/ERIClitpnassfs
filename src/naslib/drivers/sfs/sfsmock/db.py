##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the implementation of the SfsMockDb class for specific
behavior in SFS Server.
"""

import re

from .dbresources import SfsMockDbFilesystem, SfsMockDbShare, SfsMockDbDisk, \
                         SfsMockDbCache, SfsMockDbPool, SfsMockDbSnapshot

from ....nasmock.db import MockDb, register_db_resources


@register_db_resources(SfsMockDbFilesystem, SfsMockDbShare, SfsMockDbDisk,
                       SfsMockDbCache, SfsMockDbPool, SfsMockDbSnapshot)
class SfsMockDb(MockDb):
    """ It overrides some methods of super class to:
     - prepare commands before using them to execute;
     - to force some specific outputs to be returned;
     - to give a proper message format according to the SFS behavior.
    """

    clish_strip_cmd_regex = re.compile(r".*-c\s+'(.*)'$")

    def prepare_command(self, cmd):
        """ Basically removes prefixes from a command that won't be useful for
        SshClientMock.execute method. The base Sfs class uses the "clish"
        prefix for most of the commands.
        """
        cmd = super(SfsMockDb, self).prepare_command(cmd)
        match = self.clish_strip_cmd_regex.match(cmd)
        if match:
            return match.groups()[0].strip()
        return cmd.strip()

    def generic_mock_output(self, cmd):
        """ Mock some specific outputs like: "is bash" checking command, the
        SFS command to check the user privileges.
        """
        super(SfsMockDb, self).generic_mock_output(cmd)
        from ..main import Sfs
        if cmd == Sfs.is_bash_cmd:
            return 0, Sfs.string_is_bash_test, ""
        if cmd == Sfs.check_privileges_cmd % "":
            return 0, "Username      : master\nPrivileges    : Master", ""
        return None, None, None

    def error_message(self, resource, err):
        """ Overrides the base method to provide an error message in the SFS
        specific format.
        """
        super(SfsMockDb, self).error_message(resource, err)
        return "SFS %s ERROR %s" % (resource.name, str(err))
