##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
# pylint: disable=I0011,W0221,E1101,W0613
""" This module contains the abstraction implementation for UnityXT
as the resources for the UnityXT class based on the following base resources:
 - NasShareBase;
 - NasFileSystemBase;
 - NasDiskBase;
 - NasPoolBase;
 - NasCacheBase;
 - NasSnapshotBase;
 - NasServerResourceBase.

Each one of the resources classes in this module repectively based on the
NasResourceBase mentioned above has the real implementation of the following
base methods:
 - list;
 - create;
 - delete.
"""

import netaddr
from time import sleep

from ..baseresources import FileSystemResourceBase, PoolResourceBase, \
                             ShareResourceBase, DiskResourceBase, \
                             CacheResourceBase, SnapshotResourceBase, \
                             NasServerResourceBase
from ..nasexceptions import CreationException, DeletionException, \
    ResizeException, DoesNotExist
from ..resourceprops import Size
from ..log import NasLogger
from ..objects import FileSystem, Share


class ShareResource(ShareResourceBase):
    logger = NasLogger.instance().trace

    default_to_options = {
        1: 'ro',
        2: 'rw',
        3: 'no_root_squash,ro',
        4: 'no_root_squash,rw'
    }

    attrib_to_options = {
        'readOnlyHostsString': 'ro',
        'readWriteHostsString': 'rw',
        'readOnlyRootHostsString': 'no_root_squash,ro',
        'readWriteRootHostsString': 'no_root_squash,rw'
    }

    def list(self):
        """ Returns a list of Share resources items retrieved by SFS server.
        """
        response = self._nas.rest.get_type_instances(
            'nfsShare',
            [
                'name',
                'defaultAccess',
                'readOnlyHostsString',
                'readWriteHostsString',
                'readOnlyRootHostsString',
                'readWriteRootHostsString'
            ]
        )

        share_list = []
        for entry in response.json()['entries']:
            share_name = entry['content']['name']

            # If defaultAccess is not 0, then we have a share for *
            default_access = entry['content']['defaultAccess']
            if  default_access != 0:
                share_list.append(
                    self._make_share(
                        share_name,
                        "*",
                        self.default_to_options[default_access]
                    )
                )

            for attrib, options in self.attrib_to_options.items():
                if attrib in entry['content'] and \
                    entry['content'][attrib] != "":
                    for client in entry['content'][attrib].split(","):
                        share_list.append(
                            self._make_share(
                                share_name,
                                client,
                                options
                            )
                        )

        self.logger.debug(
            "unityxt.ShareResource.list: share_list=%s",
            share_list
        )

        return share_list

    def create(self, path, client, options):
        """ Creates a share with a given path, clients and options. Options
        must be a list of strings. A share is unique identified by its path
        AND its client. In case of failures it raises a CreationException.
        """
        self.logger.info(
            "unityxt.ShareResource.create path=%s, client=%s, options=%s",
            path,
            client,
            options
        )

        fs_name = path.split('/')[-1]
        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            fs_name,
            ['nfsShare', 'storageResource']
        )
        if fs_instance is None:
            raise CreationException(
                "Cannot find filesystem called %s" % fs_name
            )

        # If we already have a share, then modify it to add this client
        if 'nfsShare' in fs_instance:
            req_data = self._modify_add(path, client, options, fs_instance)
        else:
            req_data = self._modify_create(path, client, options, fs_instance)

        response = self._nas.rest.action(
            'storageResource',
            fs_instance['storageResource']['id'],
            'modifyFilesystem',
            req_data
        )
        self.logger.debug("unityxt.ShareResource.create response=%s", response)
        data = {
            'name': fs_name,
            'client': client,
            'options': options
        }
        return self._build_nas_object(**data)

    def delete(self, path, client):
        """ Deletes a Sfs Share given a path and client. A share is unique
        identified by its path AND its client. In case of failures it raises a
        DeletionException.
        """
        self.logger.info(
            "unityxt.ShareResource.delete path=%s, client=%s",
            path,
            client
        )

        share_name = path.strip('/')
        share_inst = self._nas.rest.get_type_instance_for_name(
            'nfsShare',
            share_name,
            [
                'filesystem.storageResource',
                'defaultAccess',
                'readOnlyHostsString',
                'readWriteHostsString',
                'readOnlyRootHostsString',
                'readWriteRootHostsString'
            ]
        )
        if share_inst is None:
            raise DeletionException(
                "Cannot find share for path %s" % path
            )

        from_state = {
            'defaultAccess': share_inst['defaultAccess'],
            'readOnlyHostsString': share_inst['readOnlyHostsString'],
            'readWriteHostsString': share_inst['readWriteHostsString'],
            'readOnlyRootHostsString': share_inst['readOnlyRootHostsString'],
            'readWriteRootHostsString': share_inst['readWriteRootHostsString']
        }
        to_state = ShareResource._remove_client_access(client, from_state)
        if from_state == to_state:
            raise DeletionException(
                "Cannot find client matching %s for path %s" % (
                    client,
                    path
                )
            )

        # Now figure out if there's any remain clients of this share
        # and what attributes have to be updated if we're keeping the share.
        modified_attrib = {}
        share_required = False
        for attrib in from_state.keys():
            if from_state[attrib] != to_state[attrib]:
                modified_attrib[attrib] = to_state[attrib]
            if attrib == 'defaultAccess':
                if to_state[attrib] != 0:
                    share_required = True
            elif to_state[attrib] != '':
                share_required = True
            self.logger.info(
                "ShareResource.delete attrib=%s, from=%s to=%s req=%s",
                attrib,
                from_state[attrib],
                to_state[attrib],
                share_required
            )

        request_data = ShareResource._make_del_share_req_data(
            share_required,
            modified_attrib,
            share_inst['id']
        )

        response = self._nas.rest.action(
            'storageResource',
            share_inst['filesystem']['storageResource']['id'],
            'modifyFilesystem',
            request_data
        )
        self.logger.debug("unityxt.ShareResource.delete response=%s", response)

    def _modify_create(self, path, client, options, fs_instance):
        (default_access, attrib) = self._parse_options(client, options)
        param = {
            'isReadOnly': False,
            'defaultAccess': 0,  # NoAccess
            'exportOption': 1  # Access defined in hostString attribs
        }
        if default_access is not None:
            param['defaultAccess'] = default_access
        else:
            param[attrib] = client

        return  {
            'nfsShareCreate': [
                {
                    'name': path.strip('/'),
                    'path': '/',
                    'nfsShareParameters': param
                }
            ]
        }

    def _modify_add(self, path, client, options, fs_instance):
        (default_access, update_attrib) = self._parse_options(client, options)

        share_instance = self._nas.rest.get_type_instance_for_id(
            'nfsShare',
            fs_instance['nfsShare'][0]['id'],
            [
                'defaultAccess',
                'readOnlyHostsString',
                'readWriteHostsString',
                'readOnlyRootHostsString',
                'readWriteRootHostsString'
            ]
        )

        if default_access is not None:
            # Verify that defaultAccess isn't already set
            if share_instance['defaultAccess'] != 0:
                raise Share.AlreadyExists(
                    'Share already exists for %s for client %s' % (
                        path,
                        client
                    )
                )
            param = {
                'defaultAccess': default_access
            }
        else:
            if self._client_already_exists(client, share_instance):
                raise Share.AlreadyExists(
                    'Share already exists for %s for client %s' % (
                        path,
                        client
                    )
                )
            attrib_value = ''
            if update_attrib in share_instance:
                attrib_value = share_instance[update_attrib]
            attrib_value = ",".join([attrib_value, client])
            param = {
                update_attrib: attrib_value
            }

        return {
            'nfsShareModify': [
                {
                    'nfsShare': {
                        'id': share_instance['id'],
                    },
                    'nfsShareParameters': param
                }
            ]
        }

    @staticmethod
    def _client_already_exists(client, share_instance):
        # Verify client isn't already contained in one of the access lists
        # UnityXT replaces any netmask len formats with the actual netmask
        search_client = client
        if '/' in search_client:
            ip = netaddr.IPNetwork(search_client)
            search_client = "%s/%s" % (ip.network, ip.netmask)
        ShareResource.logger.debug(
            "ShareResource._client_already_exists searching for client %s",
            search_client
        )
        match_found = False
        for attrib in ShareResource.attrib_to_options:
            if attrib in share_instance and \
                ShareResource._contains_client(
                    search_client,
                    share_instance[attrib]
                ):
                match_found = True
        ShareResource.logger.debug(
            "ShareResource._client_already_exists match_found=%s",
            match_found
        )
        return match_found

    @staticmethod
    def _contains_client(client, value):
        for one_client in value.split(','):
            if one_client == client:
                return True
        return False

    def _parse_options(self, client, options):
        default_access = None
        attrib = None

        all_option_list = options.split(",")
        relevant_options = []
        if 'no_root_squash' in all_option_list:
            relevant_options.append("no_root_squash")
        if 'rw' in all_option_list:
            relevant_options.append("rw")
        else:
            relevant_options.append("ro")
        relevant_options_str = ",".join(relevant_options)

        if client == "*":
            for value, option_str in self.default_to_options.items():
                if option_str == relevant_options_str:
                    default_access = value
        else:
            for value, option_str in self.attrib_to_options.items():
                if option_str == relevant_options_str:
                    attrib = value
        self.logger.debug(
            "ShareResource._parse_options: default_access=%s attrib=%s",
            default_access,
            attrib
        )
        return (default_access, attrib)

    def _make_share(self, name, client, options):
        return_options = "%s,nordirplus,sync" % options
        data = {
            'name': name,
            'client': client,
            'options': return_options
        }
        return self._build_nas_object(**data)

    @staticmethod
    def _remove_client_access(client, from_state):
        to_state = from_state.copy()

        # For the * client, we set defaultAccess to zero (no access)
        if client == "*" and to_state['defaultAccess'] != 0:
            to_state['defaultAccess'] = 0
        else:
            # If the client is in the form ip/subnet_length, we need to
            # convert it to ip/subnet_mask because this is the way unityxt
            # stores it
            search_client = client
            if '/' in search_client:
                ip = netaddr.IPNetwork(search_client)
                search_client = "%s/%s" % (ip.network, ip.netmask)
            ShareResource.logger.debug(
                "ShareResource._remove_client_access searching for client %s",
                search_client
            )

            for access_attrib in ShareResource.attrib_to_options:
                to_state[access_attrib] = ShareResource._remove_client(
                    search_client,
                    from_state[access_attrib]
                )

        ShareResource.logger.debug(
            "ShareResource._remove_client_access client=%s to_state=%s",
            client,
            to_state
        )

        return to_state

    @staticmethod
    def _remove_client(client, value):
        non_matches = []
        for one_client in value.split(','):
            if one_client != client:
                non_matches.append(one_client)
        result = ",".join(non_matches)
        ShareResource.logger.debug(
            "ShareResource._remove_client client=%s value=%s result=%s",
            client,
            value,
            result
        )
        return result

    # Now we need to figure out if we're modifying the share to remove the
    # client or we're removing the share because there's no one left
    # using it
    @staticmethod
    def _make_del_share_req_data(share_required, updated_attrib, share_id):
        if share_required:
            request_data = {
                'nfsShareModify': [
                    {
                        'nfsShare': {
                            'id': share_id
                        },
                        'nfsShareParameters': updated_attrib
                    }
                ]
            }
        else:
            request_data = {
                'nfsShareDelete': [
                    {
                        'nfsShare': {
                            'id': share_id
                        }
                    }
                ]
            }

        return request_data


class FileSystemResource(FileSystemResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    file system resource.
    """

    logger = NasLogger.instance().trace

    def list(self):
        """ Returns a list of FileSystems resources items retrieved by SFS
        server.
        """
        response = self._nas.rest.get_type_instances(
            'filesystem',
            ['name', 'sizeTotal', 'pool.name', 'nasServer.name']
        )
        filessystem_list = []
        for entry in response.json()['entries']:
            data = {
                'name': entry['content']['name'],
                'size': "{0}b".format(entry['content']['sizeTotal']),
                'pool': entry['content']['pool']['name'],
                'layout': entry['content']['nasServer']['name'],
                'online': True
            }
            filessystem_list.append(self._build_nas_object(**data))

        return filessystem_list

    def usage(self):
        """ Returns a list of FileSystems with usage as X%.
        """
        response = self._nas.rest.get_type_instances(
            'filesystem',
            ['name', 'sizeTotal', 'sizeUsed']
        )
        usage = []
        for entry in response.json()['entries']:
            data = {
                'FileSystem': entry['content']['name'],
                'Use%': str(
                    round(float(entry['content']['sizeUsed']) \
                    / float(entry['content']['sizeTotal']) * 100, 1)) + "%"
            }
            usage.append(data)

        return usage

    def create(self, name, size, pool, layout='simple',
               data_reduction_enabled='true'):
        self.logger.info(
            "unityxt.FS.create name=%s, size=%s, pool=%s, "
            "layout=%s, data_reduction_enabled=%s",
            name,
            size,
            pool,
            layout,
            data_reduction_enabled
        )
        if data_reduction_enabled == "true":
            is_data_reduction_enabled = True
        elif data_reduction_enabled == "false":
            is_data_reduction_enabled = False
        else:
            raise CreationException(
                'Data reduction must be set to "true" or "false"'
            )
        fs_instance = self._nas.rest.get_id_for_name(
            'filesystem',
            name
        )
        self.logger.debug('Check if fs %s exists' % fs_instance)
        if fs_instance is not None:
            raise FileSystem.AlreadyExists(
                "Filesystem %s already exists" % name
            )
        pool_id = self._nas.rest.get_id_for_name(
            'pool',
            pool
        )
        if pool_id is None:
            raise CreationException('Cannot find pool called %s' % pool)

        nas_id = self._nas.rest.get_id_for_name(
            'nasServer',
            layout
        )
        if nas_id is None:
            raise CreationException('Cannot find nasServer called %s' % layout)

        request_data = {
            'name': name,
            'fsParameters': {
                'pool': {'id': pool_id},
                'nasServer': {'id': nas_id},
                'supportedProtocols': 0,  # NFS
                'flrVersion': 0,  # OFF
                'isThinEnabled': True,
                'isDataReductionEnabled': is_data_reduction_enabled,
                'size': int(Size(size).num_bytes)
            }
        }
        response = self._nas.rest.create_post(
            "/api/types/storageResource/action/createFilesystem",
            request_data
        )
        fs_id = response.json()['content']['storageResource']['id']
        self.logger.debug("unityxt.FS.create: fs_id=%s", fs_id)

        return self._build_nas_object(
            name=name,
            size=size,
            pool=pool,
            layout=layout,
            online=True
        )

    def delete(self, name):
        """ Deletes a SFS FileSystem given a fs name. In case of failures it
        raises a NasDeletionException.
        """
        self.logger.info("unityxt.FS.delete name=%s", name)
        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            name,
            ['storageResource']
        )
        if fs_instance is None:
            raise DeletionException(
                'Cannot find file system called %s' % name
            )
        self._nas.rest.delete_instance(
            'storageResource',
            fs_instance['storageResource']['id']
        )
        self.logger.debug("unityxt.FS.delete completed for %s", name)

    def resize(self, name, size, pool=None):
        self.logger.info("unityxt.FS.resize name=%s size=%s", name, size)
        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            name,
            ['storageResource']
        )
        if fs_instance is None:
            raise ResizeException(
                'Cannot find file system called %s' % name
            )

        req_data = {
            'fsParameters': {
                'size': int(Size(size).num_bytes)
            }
        }
        self._nas.rest.action(
            'storageResource',
            fs_instance['storageResource']['id'],
            'modifyFilesystem',
            req_data
        )

    def change_data_reduction(self, name, data_reduction_enabled):
        """ Enables or disables data reduction on an existing filesystem
        """
        self.logger.info("unityxt.FS.change_data_reduction change to: %s",
                         data_reduction_enabled)
        if data_reduction_enabled == "true":
            is_data_reduction_enabled = True
        elif data_reduction_enabled == "false":
            is_data_reduction_enabled = False
        else:
            raise ResizeException(
                'Data reduction must be "true" or "false"'
            )
        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            name,
            ['storageResource', 'isDataReductionEnabled']
        )
        if fs_instance is None:
            raise DoesNotExist(
                'Cannot find file system called %s' % name
            )
        req_data = {
            'fsParameters': {
                'isDataReductionEnabled': is_data_reduction_enabled
            }
        }

        current_data_reduction = fs_instance['isDataReductionEnabled']
        if current_data_reduction != is_data_reduction_enabled:
            self._nas.rest.action(
                'storageResource',
                fs_instance['storageResource']['id'],
                'modifyFilesystem',
                req_data
            )

    def online(self, name, online=True):
        """ Method to set the file system as online or offline.
        """
        self.logger.info("online name=%s online=%s", name, online)

    def is_restore_running(self, filesystem):
        """ Checks for a running snapshot restore job for any UnityXT
            filesystem.

            Limitations

            It is currently not possible to identify the filesystem
            being restored from the REST response. As UnityXT snapshot restore
            jobs are short lived, checking for any running filesystem restore
            jobs improves the odds of detecting a running ENM rollback workflow
            but will also pick up snapshot restore jobs from a deployment
            sharing the UnityXT.

            In-progress LUN restore jobs are also picked up by the job filter.
        """
        self.logger.info("unityxt.FS.is_restore_running: filesystem=%s",
            filesystem)

        response = self._nas.rest.get_type_instances(
            'job',
            fields=['description', 'state'],
            filter_arg=[
                'description lk "restore snapshot" '
                'and ( state le 3 OR state eq 6 )'
            ]
        )

        if response.json()['entries']:
            for entry in response.json()['entries']:
                self.logger.info("unityxt.FS.is_restore_running: "
                    "A restore snapshot job is running with job id=%s",
                    entry['content']['id'])
            return True

        self.logger.info("unityxt.FS.is_restore_running: "
                "No running restore snapshot jobs were detected.")
        return False


class SnapshotResource(SnapshotResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
        snapshot resource.
    """
    logger = NasLogger.instance().trace

    def list(self):
        """ Returns a list of snapshot resources items retrieved by SFS server.
        """
        response = self._nas.rest.get_type_instances(
            'snap',
            ['name', 'storageResource.name', 'creationTime'],
            ['storageResource.type==1']
        )

        results = []
        for entry in response.json()['entries']:
            ec = entry['content']
            data = {
                'name': ec['name'],
                'filesystem': ec['storageResource']['name'],
                'cache': None,
                'date': ec['creationTime'],
                'snaptype': ""
            }
            results.append(self._build_nas_object(**data))

        return results

    def create(self, name, filesystem, cache):
        """ Creates a snapshot (rollback) on SFS server given a snapshot name,
        file system name and a cache object name. In case of failures it raises
        relevant Exception.
        """
        self.logger.info(
            "unityxt.SS.create name=%s filesystem=%s",
            name,
            filesystem
        )

        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            filesystem,
            ['storageResource']
        )
        if fs_instance is None:
            raise DoesNotExist(
                'Cannot find file system called %s' % filesystem
            )

        req_data = {
            'storageResource': {
                'id': fs_instance['storageResource']['id']
            },
            'name': name
        }
        self._nas.rest.create_instance(
            'snap',
            req_data
        )
        data = {
            'name': name,
            'filesystem': filesystem,
            'cache': None
        }
        return self._build_nas_object(**data)

    def delete(self, name, filesystem):
        """ Deletes a SFS snapshot given a snapshot name and fs name.
        In case of failures it raises a Snapshot.DeletionException.
        """
        self.logger.info(
            "unityxt.SS.delete name=%s filesystem=%s",
            name,
            filesystem
        )

        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            filesystem,
            ['storageResource']
        )
        if fs_instance is None:
            self.logger.warn('Cannot find file system called %s' % filesystem)

        snap_instance = self._nas.rest.get_type_instance_for_name(
            'snap',
            name,
            ['id']
        )
        if snap_instance is None:
            self.logger.warn('Cannot find snap called %s' % name)
        else:
            self._nas.rest.delete_instance('snap', snap_instance['id'])

    def restore(self, name, filesystem):
        """ Restores the file system given a snapshot name and the file system.
        In SFS, to restore a file system, 3 steps are needed:
         1. offline the file system if it is online;
         2. restore the file system;
         3. bring the file system back to the online state.
        """
        self.logger.info(
            "unityxt.SS.restore name=%s filesystem=%s",
            name,
            filesystem
        )

        fs_instance = self._nas.rest.get_type_instance_for_name(
            'filesystem',
            filesystem,
            ['storageResource']
        )
        if fs_instance is None:
            raise DoesNotExist(
                'Cannot find file system called %s' % filesystem
            )

        snap_instance = self._nas.rest.get_type_instance_for_name(
            'snap',
            name,
            ['id']
        )
        if snap_instance is None:
            raise DoesNotExist(
                'Cannot find snap called %s' % name
            )

        response = self._nas.rest.action(
            'snap',
            snap_instance['id'],
            'restore',
            None
        )

        # Now we need to delete the snap created by the restore operation
        backup_id = response.json()['content']['backup']['id']
        self.logger.info("unityxt.SS.restore deleting backup id=%s", backup_id)
        self._nas.rest.delete_instance(
            'snap',
            backup_id
        )

    def rollbackinfo(self, name):
        """ Returns the info of snapshot resources.
        """
        self.logger.info(
            "unityxt.SS.rollbackinfo name=%s ",
            name
        )

        response = self._nas.rest.get_type_instance_for_name(
            'snap',
             name,
            ['name', 'creationTime', 'size']
        )
        if response is None:
            raise DoesNotExist(
                'Cannot find rollback info on snap called %s' % name
            )
        entry = response['name'] + " " + response['creationTime'] \
        + " " + str(response['size'])
        results = ['NAME CREATIONTIME             SIZE', entry]
        return results


class DiskResource(DiskResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    disk resource.
    """

    def list(self):
        """ Returns a list of Disk resources items retrieved by SFS server.
        """
        raise NotImplementedError

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class PoolResource(PoolResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    pool resource.
    """

    def list(self):
        """ Returns a list of Pool resources items retrieved by SFS server.
        """
        raise NotImplementedError

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError


class CacheResource(CacheResourceBase):
    """ This class contains the implementation of the basic methods of a SFS
    cache resource.
    """
    def list(self):
        """ Returns a list of Cache resources items retrieved by SFS server.
        """
        return []

    def create(self, name, size, pool):
        """ Creates a Cache with a given name, size and poll name.
        """
        raise NotImplementedError

    def delete(self, name):
        """ Deletes a SFS cache object given a cache name. In case of failures
        it raises a NasDeletionException.
        """
        raise NotImplementedError

    def resize(self, name, size, pool=None):
        """ Resizes a Cache object given a cache name and the new size.
        """
        raise NotImplementedError

    def get_related_snapshots(self, name):
        raise NotImplementedError


class NasServerResource(NasServerResourceBase):
    """ This class contains the implementation of the basic methods of a
    UnityXT NAS server resource.
    """
    sp_check_attempts = 60

    logger = NasLogger.instance().trace

    def _validate_ports(self, sp, ports):
        """ Validate that supplied ports exist and that they are in
        'UP' state
        """
        for port in ports.split(","):
            if port.isdigit():
                port_id = sp.lower() + "_ocp_0_eth" + port
                port_instance = self._nas.rest.get_type_instance_for_id(
                    'ipPort',
                    port_id,
                    [
                        'isLinkUp'
                    ]
                )
                if port_instance is None:
                    raise DoesNotExist(
                        'Cannot find port called %s' % port_id
                    )
                if port_instance['isLinkUp'] is not True:
                    raise CreationException('Port %s is not in "Up" state'
                                            % port_id)
            else:
                raise CreationException('Port %s is not numeric' % port)

        return

    def _check_ports_free(self, sp, fsn_ports):
        """ Check that the ports are not associated
        with an existing FSN
        """
        response = self._nas.rest.get_type_instances(
            'fsnPort',
            ['id', 'primaryPort', 'secondaryPorts', 'storageProcessor']
        )
        for fsn in response.json()['entries']:
            if fsn['content']['storageProcessor']['id'] == sp:
                if fsn['content']['primaryPort']['id'] in fsn_ports:
                    raise CreationException(
                        'Port %s is already in FSN %s'
                            % (fsn['content']['primaryPort']['id'],
                               fsn['content']['id'])
                    )
                for secondary_port in fsn['content']['secondaryPorts']:
                    if secondary_port['id'] in fsn_ports:
                        raise CreationException(
                            'Port %s is already in FSN %s'
                                % (secondary_port['id'],
                                   fsn['content']['id'])
                        )

        return

    def _create_fsn(self, sp, ports):
        """ Create a Fail-Safe network from the supplied ports.
        """
        self.logger.info(
            "unityxt.NS.FSN.create sp=%s, ports=%s",
            sp,
            ports
        )

        first_port = True
        existing_primary = ""
        primary_id = ""
        secondary_ids = []
        existing_secondary = []
        new_secondary = []
        fsn_id = ""
        fsn_ports = []

        self._validate_ports(sp, ports)

        for port in ports.split(","):
            port_id = sp.lower() + "_ocp_0_eth" + port
            fsn_ports.append(port_id)
            if first_port:
                primary_id = port_id
                fsn_id = sp + "_fsn_ocp_0_" + port
                first_port = False
            else:
                secondary_ids.append({'id': port_id})
                new_secondary.append(port_id)

        fsn_check = self._nas.rest.get_type_instance_for_id(
            'fsnPort',
            fsn_id,
            ['id', 'primaryPort', 'secondaryPorts']
        )

        if fsn_check is not None:
            self.logger.info(
                "unityxt.NS.FSN.create FSN %s already exists",
                fsn_id
            )
            existing_primary = fsn_check['primaryPort']['id']
            existing_secondary = []
            for secondary_port in fsn_check['secondaryPorts']:
                existing_secondary.append(secondary_port['id'])
            if (existing_primary != primary_id or
                set(existing_secondary) != set(new_secondary)):
                raise CreationException(
                    'FSN %s exists but ports are incorrect' % fsn_id
                )
            else:
                self.logger.info(
                    "unityxt.NS.FSN.create Ports correct in existing FSN %s",
                    fsn_id
                )
                self.logger.debug(
                    "unityxt.NS.FSN.create Skipping creation of FSN %s",
                    fsn_id
                )
                return fsn_id
        else:
            self._check_ports_free(sp, fsn_ports)

        request_data = {
            'primaryPort': {'id': primary_id},
            'secondaryPorts': secondary_ids
        }
        response = self._nas.rest.create_post(
            "/api/types/fsnPort/instances",
            request_data
        )
        fsn_id = response.json()['content']['id']
        self.logger.debug("unityxt.NS.FSN.create: fsn_id=%s", fsn_id)

        return fsn_id

    def _create_file_interface(self, ns, fsn, ip, netmask, gateway):
        """ Create a network interface for the Fail-Safe network.
        """
        self.logger.info(
            "unityxt.NS.FI.create ns=%s, fsn=%s, \
             ip=%s, netmask=%s, gateway=%s",
            ns,
            fsn,
            ip,
            netmask,
            gateway
        )
        response = self._nas.rest.get_type_instances(
            'fileInterface',
            ['id',
             'nasServer',
             'ipPort',
             'ipAddress',
             'netmask',
             'gateway']
        )
        for fi_entry in response.json()['entries']:
            fi_id = fi_entry['content']['id']
            if fi_entry['content']['nasServer']['id'] == ns:
                self.logger.info(
                    "unityxt.NS.FI.create File interface %s already exists",
                    fi_id
                )
                if fi_entry['content']['ipPort']['id'] != fsn or \
                   fi_entry['content']['ipAddress'] != ip or \
                   fi_entry['content']['netmask'] != netmask or \
                   fi_entry['content']['gateway'] != gateway:
                    raise CreationException(
                        'File interface %s already exists but attributes \
                         do not match requested' % fi_id
                    )
                return fi_id
            else:
                if fi_entry['content']['ipPort']['id'] == fsn or \
                   fi_entry['content']['ipAddress'] == ip:
                    raise CreationException(
                        'File interface %s using FSN %s and/or IP %s \
                         already exists but is assigned to NAS server %s'
                        % (fi_id, fsn, ip,
                           fi_entry['content']['nasServer']['id'])
                    )

        request_data = {
            'nasServer': {'id': ns},
            'ipPort': {'id': fsn},
            'ipAddress': ip,
            'netmask': netmask,
            'gateway': gateway
        }
        response = self._nas.rest.create_post(
            "/api/types/fileInterface/instances",
            request_data
        )
        fi_id = response.json()['content']['id']
        self.logger.debug("unityxt.NS.FI.create: fi_id=%s", fi_id)

        return fi_id

    def _create_nfs_server(self, ns, protocols):
        """ Create an NFS server for the NAS server
        supporting the supplied protocols.
        """
        self.logger.info(
            "unityxt.NS.NFS.create ns=%s, protocols=%s",
            ns,
            protocols
        )
        supported_protocols = ['nfsv3', 'nfsv4']
        nfsv3enabled = False
        nfsv4enabled = False
        for protocol in protocols.split(','):
            if protocol not in supported_protocols:
                raise CreationException('Protocol %s not supported' % protocol)
            elif protocol == 'nfsv3':
                nfsv3enabled = True
            elif protocol == 'nfsv4':
                nfsv4enabled = True

        response = self._nas.rest.get_type_instances(
            'nfsServer',
            ['id',
             'nasServer',
             'nfsv3Enabled',
             'nfsv4Enabled']
        )
        for nfs_entry in response.json()['entries']:
            if nfs_entry['content']['nasServer']['id'] == ns:
                nfs_id = nfs_entry['content']['id']
                self.logger.info(
                    "unityxt.NS.NFS.create NFS %s already enabled",
                    nfs_id
                )
                if nfs_entry['content']['nfsv3Enabled'] != nfsv3enabled or \
                   nfs_entry['content']['nfsv4Enabled'] != nfsv4enabled:
                    raise CreationException(
                        'Error NFS %s already enabled but protocols \
                         do not match requested' % nfs_id
                    )

                return nfs_id

        request_data = {
            'nasServer': {'id': ns},
            'nfsv3Enabled': nfsv3enabled,
            'nfsv4Enabled': nfsv4enabled
        }
        response = self._nas.rest.create_post(
            "/api/types/nfsServer/instances",
            request_data
        )
        nfs_id = response.json()['content']['id']
        self.logger.debug("unityxt.NS.NFS.create: nfs_id=%s", nfs_id)

        return nfs_id

    def _create_ndmp_server(self, ns, pw):
        """ Enable NDMP on a NAS server.
        """
        self.logger.info(
            "unityxt.NS.NDMP.create ns=%s", ns)

        response = self._nas.rest.get_type_instances(
            'fileNDMPServer',
            ['id',
             'nasServer',
             'username']
        )
        for ndmp_entry in response.json()['entries']:
            if ndmp_entry['content']['nasServer']['id'] == ns:
                ndmp_id = ndmp_entry['content']['id']
                self.logger.info(
                    "unityxt.NS.NDMP.create NDMP %s already enabled",
                    ndmp_id
                )
                self.logger.info(
                    "unityxt.NS.NDMP.create Setting NDMP %s password",
                    ndmp_id
                )
                request_data = {'password': pw}
                response = self._nas.rest.create_post(
                    "/api/instances/fileNDMPServer/" +
                    ndmp_id +
                    "/action/modify",
                    request_data
                )

                return ndmp_id

        request_data = {
            'nasServer': {'id': ns},
            'password': pw
        }
        response = self._nas.rest.create_post(
            "/api/types/fileNDMPServer/instances",
            request_data
        )
        ndmp_id = response.json()['content']['id']
        self.logger.debug("unityxt.NS.NDMP.create: ndmp_id=%s", ndmp_id)

        return ndmp_id

    def _failback_nas_server(self):
        """ Move the NAS server to the opposite SP.
        """
        response = self._nas.rest.create_post(
            "/api/instances/system/0/action/failback?timeout=2",
            None
        )
        self.logger.debug('unityxt.NS._failback_nas_server response is %s'
                           % response)

    def _failback_nas_server_check(self, name, attempts):
        """ Check if the SP has failed back successfully.
        If the NAS server is still failed over, exit as the array has an
        issue that needs fixed.

        :param name: NAS server name
        :type name: str
        :param attempts: How many times to check if the NAS server is running
        on the correct SP. This must be a positive integer of 1 or above.
        :type attempts: int
        :return: False when attempts are exhausted and currentSP does not
        equal homeSP. True if attempts are not exhausted and currentSP equals
        homeSP.
        :rtype: bool
        """
        interval = 5
        for _ in range(attempts):
            if attempts == 0:
                return False
            nas_sp_data = self._nas.rest.get_type_instance_for_name(
            'nasServer',
            name,
            ['currentSP', 'homeSP'])

            if nas_sp_data['currentSP'] == nas_sp_data['homeSP']:
                self.logger.info("unityXT.NS._fnsc: SP is correct for " \
                                  "server %s" % name)
                return True
            else:
                self.logger.info("unityXT.NS._fnsc: SP incorrect for " \
                                  "server %s, running on %s instead of %s"
                                  % (name,
                                     nas_sp_data['currentSP'],
                                     nas_sp_data['homeSP']))
            self.logger.info("unityXT.NS._fnsc: Pause for %s seconds to " \
                              "check failback" % interval)
            sleep(interval)
            attempts -= 1

    def create(self, name, pool, ports, network, protocols, ndmp_pass):
        """ Create a NAS server.
        ports parameter is comma separated string, e.g. "0,2".
        network parameter is a comma separated string which must have
        4 fields "sp,ip,netmask,gateway".
        """

        network_items = network.split(",")
        if len(network_items) != 4:
            raise CreationException(
                'Missing network parameter entries. \
                 Required: "sp,ip,netmask,gateway" \
                 Supplied: %s' % network
            )
        sp = network_items[0]
        ip = network_items[1]
        netmask = network_items[2]
        gateway = network_items[3]

        self.logger.info(
            "unityxt.NS.create name=%s, pool=%s, sp=%s, \
             ports=%s, ip=%s, netmask=%s, gateway=%s, \
             protocols=%s, ndmp_pass",
            name,
            pool,
            sp,
            ports,
            ip,
            netmask,
            gateway,
            protocols
        )

        fsn_id = self._create_fsn(sp, ports)

        ns_exists = False

        pool_id = self._nas.rest.get_id_for_name(
            'pool',
            pool
        )
        if pool_id is None:
            raise DoesNotExist(
                'Cannot find pool called %s' % pool
            )

        sp_id = self._nas.rest.get_type_instance_for_id(
            'storageProcessor',
            sp,
            ''
        )
        if sp_id is None:
            raise DoesNotExist(
                'Cannot find SP called %s' % sp
            )

        response = self._nas.rest.get_type_instances(
            'nasServer',
            ['id',
             'pool',
             'homeSP',
             'name']
        )
        for ns_entry in response.json()['entries']:
            if ns_entry['content']['name'] == name:
                ns_id = ns_entry['content']['id']
                ns_exists = True
                if ns_entry['content']['homeSP']['id'] != sp:
                    raise CreationException(
                        'NAS server exists on incorrect SP %s'
                        % ns_entry['content']['homeSP']['id']
                    )
                elif ns_entry['content']['pool']['id'] != pool_id:
                    raise CreationException(
                        'NAS server exists on incorrect pool %s'
                        % ns_entry['content']['pool']['id']
                    )
                else:
                    self.logger.info(
                        "unityxt.NS.create NAS server already exists, \
                         skipping creation"
                    )

        if not ns_exists:
            request_data = {
                'name': name,
                'pool': {'id': pool_id},
                'homeSP': sp_id
            }
            response = self._nas.rest.create_post(
                "/api/types/nasServer/instances",
                request_data
            )
            ns_id = response.json()['content']['id']
            self.logger.debug("unityxt.NS.create: ns_id=%s", ns_id)

        self._create_file_interface(ns_id, fsn_id,
                                    ip, netmask, gateway)

        self._create_nfs_server(ns_id, protocols)
        # Check that NAS server has created on the intended SP and is not
        # failed over.
        if not self._failback_nas_server_check(name, 1):
            self.logger.info("unityxt.NS.create: NAS Server %s running on \
                             incorrect SP" % (name))
            self._failback_nas_server()

            if not self._failback_nas_server_check(name,
                                                NasServerResource.
                                                sp_check_attempts):
                raise CreationException("Unable to failback NAS Server %s"
                                        % name)

        self._create_ndmp_server(ns_id, ndmp_pass)

        return self._build_nas_object(
            name=name,
            pool=pool,
            homesp=sp
        )

    def _delete_fsn(self, fsn_id):
        """ Deletes a Fail-Safe network.
        """
        self.logger.info("unityxt.NS.FSN.delete fsn_id=%s", fsn_id)
        self._nas.rest.delete_instance(
            'fsnPort',
            fsn_id
        )
        self.logger.debug("unityxt.NS.FSN.delete completed for %s", fsn_id)

    def delete(self, name):
        """ Deletes a NAS server.
        """
        self.logger.info("unityxt.NS.delete name=%s", name)
        ns_instance = self._nas.rest.get_type_instance_for_name(
            'nasServer',
            name,
            ['id', 'fileInterface.ipPort']
        )
        if ns_instance is None:
            self.logger.info(
                "unityxt.NS.delete NAS server %s does not exist, \
                 skipping deletion",
                name
            )

            return

        if "fileInterface" in ns_instance:
            if "ipPort" in ns_instance['fileInterface'][0]:
                fsn_id = ns_instance['fileInterface'][0]['ipPort']['id']
            else:
                fsn_id = None
        else:
            fsn_id = None

        self._nas.rest.delete_instance(
            'nasServer',
            ns_instance['id']
        )
        self.logger.debug("unityxt.NS.delete completed for %s", name)

        if fsn_id and "fsn" in fsn_id:
            self._delete_fsn(fsn_id)

    def list(self):
        """ Returns a list of NAS servers.
        """
        response = self._nas.rest.get_type_instances(
            'nasServer',
            ['name', 'pool.name', 'homeSP.id']
        )
        nasserver_list = []
        for entry in response.json()['entries']:
            data = {
                'name': entry['content']['name'],
                'pool': entry['content']['pool']['name'],
                'homesp': entry['content']['homeSP']['id']
            }
            nasserver_list.append(self._build_nas_object(**data))

        return nasserver_list

    def get_nasserver_details(self, name):
        """ Gets details of a NAS server.
        """
        ns_attrs = [
            'id',
            'name',
            'health',
            'homeSP',
            'currentSP',
            'pool.name',
            'sizeAllocated',
            'fileSpaceUsed',
            'fileInterface.ipPort',
            'fileInterface.ipAddress',
            'fileInterface.netmask',
            'fileInterface.gateway',
            'filesystems',
            'nfsServer.nfsv3Enabled',
            'nfsServer.nfsv4Enabled'
        ]

        nasserver_details = self._nas.rest.get_type_instance_for_name(
            'nasServer',
            name,
            ns_attrs
        )
        if nasserver_details is None:
            raise DoesNotExist(
                'Cannot find NAS Server called %s' % name
            )

        return nasserver_details

    def change_sharing_protocol(self, protocols):
        """ Change the nfs sharing protocols
        """
        self.logger.info(
            "unityxt.NS.NFS.modify protocols=%s",
            protocols
        )
        nfsv3enabled = False
        nfsv4enabled = False
        for protocol in protocols.split(','):
            if protocol == 'nfsv3':
                nfsv3enabled = True
            elif protocol == 'nfsv4':
                nfsv4enabled = True

        response = self._nas.rest.get_type_instances(
            'nfsServer',
            ['id',
             'nasServer',
             'nfsv3Enabled',
             'nfsv4Enabled']
        )

        for nfs_entry in response.json()['entries']:
            ns = nfs_entry['content']['nasServer']['id']
            nfs_id = nfs_entry['content']['id']
            self.logger.info(
                "unityxt.NS.NFS.modify ns=%s, protocols=%s",
                ns,
                protocols
            )
            if nfs_entry['content']['nfsv3Enabled'] != nfsv3enabled or \
               nfs_entry['content']['nfsv4Enabled'] != nfsv4enabled:

                request_data = {
                    'nfsv3Enabled': nfsv3enabled,
                    'nfsv4Enabled': nfsv4enabled
                }
                response = self._nas.rest.create_post(
                    "/api/instances/nfsServer/" +
                    nfs_id +
                    "/action/modify",
                    request_data
                )
