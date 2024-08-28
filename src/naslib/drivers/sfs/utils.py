##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains for some Symantec "vx*" commands. It has the
VxCommands class that provides some util methods for the commands mentioned.
"""

import re

from ...log import NasLogger
from .parsers import VxPrintOutput, VxPropertiesOutputParser, \
                     VxGenericListOutput


class VxCommandsException(Exception):
    pass


class VxCommands(object):
    """ Class helper for Symantec "vx*" commands.
    """
    logger = NasLogger.instance()
    align_regex = re.compile(r"(\d+)\s+\(bytes\)")

    def __init__(self, nas):
        """ This constructor sets the main nas instance.
        """
        self._nas = nas

    def __repr__(self):
        """ Returns the representative string of this object.
        >>> VxCommands("<Some NasBase object>")
        <VxCommands>
        """
        return "<%s>" % self.__class__.__name__

    @property
    def nas(self):
        """ Property to access the nas instance of the NasBase subclass, the
        parent instance.
        """
        return self._nas

    def debug(self, msg):
        """ Helper method for debug log messages.
        """
        return self.logger.trace.debug("VxCommands: %s" % msg)

    def execute(self, cmd):
        """ Executes a "vx*" command and raises the proper exception in case
        of errors.
        """
        _, out, err = self.nas.ssh.run(cmd)
        if err:
            msg = 'ERROR while trying to execute command "%s": %s' % (cmd, err)
            self.debug(msg)
            raise VxCommandsException(msg)
        else:
            self.debug("executed %s command successfully" % cmd)
        return out

    def execute_cmd(self, cmd):
        """ Executes a shell command and raises the proper exception in case
        of errors.
        """
        rc, out, err = self.nas.ssh.run(cmd)
        if err:
            msg = 'ERROR %s while trying to execute command " \
                   %s": %s' % (rc, cmd, err)
            self.debug(msg)
            raise VxCommandsException(msg)
        else:
            self.debug("executed %s command successfully" % cmd)
        return out

    def get_disk_group_id(self, disk):
        """ Given a disk name, retrieves its group id.
        """
        properties = self.vdisk_list(disk)
        try:
            return properties['group']['id']
        except (KeyError, TypeError), err:
            msg = 'Could not get the group id from disk %s: %s' % (disk, err)
            self.debug(msg)
            raise VxCommandsException(msg)

    def get_group_properties(self, group_id):
        """ Retrieves information data regarding the specified disk group id.
        """
        out = self.execute('vxdg -q list %s' % group_id)
        parser = VxPropertiesOutputParser(out)
        return parser.parse()

    def vdisk_list(self, disk):
        """ Retrieves information data regarding the specified disk name.
        """
        out = self.execute('vxdisk list %s' % disk)
        parser = VxPropertiesOutputParser(out)
        return parser.parse()

    def vdisk_listtag(self):
        """ Retrieves information data  that associates disks to tags (Pools).
        """
        out = self.execute('vxdisk listtag')
        parser = VxGenericListOutput(out, 'device')
        return parser.parse()

    def vxedit(self, cachename1):
        """ Using the vxedit command to remove the volumes
        """
        out = self.execute('vxedit -rf rm %s_tier1' % cachename1)
        return out

    def vxprint_simple(self):
        """ Retrieves all the information in SFS through vxprint command.
        """
        out = self.execute("vxprint")
        parser = VxPrintOutput(out)
        return parser.parse()

    def vxprint(self, fs_name=""):
        """ Retrieves all information from a file system in SFS through the
        vxprint command. If fs_name is an empty string, retrieves all
        all file systems' information.
        """
        out = self.execute(
            "vxprint -hrAF sd:'%type %name %assoc %kstate %len "
            "%column_pl_offset %state %tutil0 %putil0 %device'{0}".
            format(" " + fs_name if fs_name else ""))
        parser = VxPrintOutput(out)
        data = parser.parse()
        if fs_name:
            return data[fs_name]
        return data

    def cache_grow(self, name, size):
        """ Perform Volume Manager cache grow size.
        """
        cmd = 'vxcache growcacheto %s %s' % (name, size)
        self.execute(cmd)

    def get_pools_disks_from_object(self, name):
        """ Retrieves the list of disk and pools used by the provided SFS/VA
        object (file system, cache, snapshot). First parses the vxprint output
        taking the 'sd' (subdisks) values. Then for each disk,
        gets the vx tags (pools) related.
        """
        self.debug('Running get_pools_disks_from_object for "%s"' % name)
        data = self.vxprint(name)
        self.debug('vxprint data for "%s": %s' % (name, data))
        # This is the case for filesystems and cache objects on NAS server
        if 'sd' in data:
            disks = [sd['device'] for sd in data['sd']]
        # This is the case for snapshots objects on NAS server
        elif 'sd' in data['dc']:
            disks = [sd['device'] for sd in data['dc']['sd']]
        self.debug('disks for "%s": %s' % (name, disks))
        disks_pools = self.vdisk_listtag()
        self.debug('disks_pools for "%s": %s' % (name, disks_pools))
        pools = list(set([disks_pools[d]['value'] for d in disks]))
        self.debug('pools for "%s": %s' % (name, pools))
        return disks, pools

    def get_pool_by_cache(self, name):
        """ Retrieves a single pool associated to the given cache object.

        **NOTE** Assuming here that the cache object was created with only
        a single pool. Even if the cache is associated to more than one pool,
        this method will return just one pool name anyway, taking the first one
        from the list.
        """
        return self.get_pools_disks_from_object(name)[1][0]
