##############################################################################
# COPYRIGHT Ericsson AB 2022
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
from src.naslib.unityxt.mock_requests import UnityRESTMocker
from naslib.unityxt.mock_requests import UnityRESTMocker
from naslib.unityxt.unityrest import UnityREST
from naslib.connection import NasConnection
from naslib.nasexceptions import CreationException, DeletionException, \
    ResizeException, DoesNotExist, NasExecCommandException, NasConnectionException
from naslib.objects import FileSystem, Share

import json
import logging
import logging.handlers
import unittest
import pprint
import requests
from mock import patch

class TestUnityXT(unittest.TestCase):
    logging_setup = False

    #
    # File system tests
    #
    def test_is_restore_running_false(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/job/instances?filter=description lk "restore snapshot" '
            'and ( state le 3 OR state eq 6 )&fields=description,state',
            None,
            200,
            {
                'entries': []
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertFalse(driver.filesystem.is_restore_running("test_fs"))

    def test_is_restore_running_true(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/job/instances?filter=description lk "restore snapshot" '
            'and ( state le 3 OR state eq 6 )&fields=description,state',
            None,
            200,
            {
                'entries': [
                    {
                         'content': {
                             "id": "job_123",
                             "state": 2,
                             "description": "Restore snapshot"
                         }
                    }
                ]
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertTrue(driver.filesystem.is_restore_running("test_fs"))

    def test_fs_list(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/filesystem/instances?fields=name,sizeTotal,pool.name,nasServer.name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'fs_1',
                            'name': 'filesystem1',
                            'sizeTotal': 1048576,
                            'pool': {
                                'name': 'pool_1'
                            },
                            'nasServer': {
                                'name' : 'nas_1'
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            filesystems = driver.filesystem.list()
            self.assertTrue(len(filesystems) == 1)
            pprint.pprint(filesystems)
            self.assertEqual(filesystems[0].name, "filesystem1")
            self.assertEqual(filesystems[0].layout, "nas_1")

    def test_fs_create(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                        'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:test_pool?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:test_nas?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/types/storageResource/action/createFilesystem',
            {
                'fsParameters': {
                    'isDataReductionEnabled': True,
                    'isThinEnabled': True,
                    'supportedProtocols': 0, # NFS
                    'flrVersion': 0, # OFF
                    'pool': {
                        'id': 'pool_1'
                    },
                    'nasServer': {
                        'id': 'nas_1'
                    },
                    'size': 1073741824,
                },
                'name': 'test_fs',
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            filesystem = driver.filesystem.create("test_fs", "1G", "test_pool", "test_nas")
            self.assertEqual(filesystem.name, "test_fs")
            self.assertEqual(filesystem.layout, "test_nas")

    def test_fs_create_fail(self):
        # Something goes wrong during the final create action
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                        'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:test_pool?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:test_nas?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/types/storageResource/action/createFilesystem',
            {
                'fsParameters': {
                    'isDataReductionEnabled': True,
                    'isThinEnabled': True,
                    'supportedProtocols': 0, # NFS
                    'flrVersion': 0, # OFF
                    'pool': {
                        'id': 'pool_1'
                    },
                    'nasServer': {
                        'id': 'nas_1'
                    },
                    'size': 1073741824,
                },
                'name': 'test_fs',
            },
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                NasExecCommandException,
                driver.filesystem.create,
                "test_fs",
                "1G",
                "test_pool",
                "test_nas"
            )

    def test_fs_create_badpool(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                        'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:test_pool?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.filesystem.create,
                "test_fs",
                "1G",
                "test_pool",
                "test_nas"
            )

    def test_fs_create_badnas(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                        'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:test_pool?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:test_nas?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.filesystem.create,
                "test_fs",
                "1G",
                "test_pool",
                "test_nas"
            )

    def test_fs_create_fs_already_exists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1'
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                FileSystem.AlreadyExists,
                driver.filesystem.create,
                "test_fs",
                "1G",
                "test_pool",
                "test_nas"
            )

    def test_fs_create_dr_false(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                        'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:test_pool?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:test_nas?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/types/storageResource/action/createFilesystem',
            {
                'fsParameters': {
                    'isDataReductionEnabled': False,
                    'isThinEnabled': True,
                    'supportedProtocols': 0, # NFS
                    'flrVersion': 0, # OFF
                    'pool': {
                        'id': 'pool_1'
                    },
                    'nasServer': {
                        'id': 'nas_1'
                    },
                    'size': 1073741824,
                },
                'name': 'test_fs',
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            filesystem = driver.filesystem.create("test_fs", "1G", "test_pool", "test_nas", "false")
            self.assertEqual(filesystem.name, "test_fs")

    def test_fs_create_with_dr_bad_param(self):
        self.initMock()
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.filesystem.create,
                "test_fs",
                "1G",
                "test_pool",
                "test_nas",
                "bad"
            )

    def test_fs_delete(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/storageResource/res_1',
            None,
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            share = driver.filesystem.delete("test_fs")

    def test_fs_delete_notexist(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DeletionException,
                driver.filesystem.delete,
                "test_fs"
            )

    def test_fs_delete_fail(self):
        # Something goes wrong when calling the delete of the FS
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/storageResource/res_1',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                NasExecCommandException,
                driver.filesystem.delete,
                "test_fs"
            )

    def test_fs_resize(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'fsParameters': {
                    'size': 10737418240
                }
            },
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.filesystem.resize("test_fs", "10G")

    def test_fs_resize_notexists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                ResizeException,
                driver.filesystem.resize,
                "test_fs",
                "10G"
            )

    def test_fs_online(self):
        self.initMock()
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.filesystem.online("test_fs", True)

    def test_fs_usage(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/filesystem/instances?fields=name,sizeTotal,sizeUsed',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'fs_1',
                            'name': 'filesystem1',
                            'sizeTotal': 1234560,
                            'sizeUsed': 123456
                        }
                    }
                ]
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            filesystem_usage = driver.filesystem.usage()
            self.assertEqual(filesystem_usage[0]['Use%'], "10.0%")

    def test_fs_change_data_reduction_false(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource,isDataReductionEnabled',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'isDataReductionEnabled': 'true',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'fsParameters': {
                    'isDataReductionEnabled': False
                }
            },
            204,
            None
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.filesystem.change_data_reduction("test_fs", "false")

    def test_fs_change_data_reduction_true(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource,isDataReductionEnabled',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'isDataReductionEnabled': 'true',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'fsParameters': {
                    'isDataReductionEnabled': True
                }
            },
            204,
            None
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.filesystem.change_data_reduction("test_fs", "true")

    def test_fs_change_data_reduction_notexists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource,isDataReductionEnabled',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.filesystem.change_data_reduction,
                "test_fs",
                "false"
            )

    def test_fs_change_data_reduction_bad_param(self):
        self.initMock()
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                ResizeException,
                driver.filesystem.change_data_reduction,
                "test_fs",
                "bad"
            )

    #
    # Share tests
    #
    def test_share_list(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsShare/instances?fields=name,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'sr_1',
                            'name': 'test_fs',
                            'defaultAccess': 1,
                            'readWriteRootHostsString': "1.2.3.0/24"
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            shares = driver.share.list()
            self.assertTrue(len(shares) == 2)
            for share in shares:
                self.assertEqual(share.name, "test_fs")
                self.assertTrue(
                    share.client == "1.2.3.0/24" or share.client == "*"
                )

    def test_share_create_new(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareCreate': [
                    {
                        'name': 'vx/test_fs',
                        'path': '/',
                        'nfsShareParameters': {
                            'isReadOnly': False,
                            'defaultAccess': 0,  # NoAccess
                            'exportOption': 1,
                            'readWriteRootHostsString': "1.2.3.0/24"
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            share = driver.share.create("/vx/test_fs", "1.2.3.0/24", "rw,no_root_squash")
            self.assertEqual(share.name, "test_fs")
            self.assertEqual(share.client, "1.2.3.0/24")

    def test_share_create_modify(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    },
                    'nfsShare': [{
                        'id': 'NFSShare_1'
                    }]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/NFSShare_1?fields=defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0",
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareModify': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        },
                        'nfsShareParameters': {
                            'readWriteRootHostsString': '1.2.3.0/255.255.255.0,1.2.4.0/24'
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            share = driver.share.create("/vx/test_fs", "1.2.4.0/24", "rw,no_root_squash")
            pprint.pprint(share)
            self.assertEqual(share.name, "test_fs")
            self.assertEqual(share.client, "1.2.4.0/24")

    def test_share_create_new_wild(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareCreate': [
                    {
                        'name': 'test_fs',
                        'path': '/',
                        'nfsShareParameters': {
                            'isReadOnly': False,
                            'defaultAccess': 1,
                            'exportOption': 1,
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            share = driver.share.create("test_fs", "*", "ro")
            pprint.pprint(share)
            self.assertEqual(share.name, "test_fs")
            self.assertEqual(share.client, "*")

    def test_share_create_modify_wild(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    },
                    'nfsShare': [{
                        'id': 'NFSShare_1'
                    }]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/NFSShare_1?fields=defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 0,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0",
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareModify': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        },
                        'nfsShareParameters': {
                            'defaultAccess': 1
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            share = driver.share.create("test_fs", "*", "ro")
            pprint.pprint(share)
            self.assertEqual(share.name, "test_fs")
            self.assertEqual(share.client, "*")

    def test_share_create_badfs(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.share.create,
                "/test_fs",
                "1.2.3.0/24",
                "rw,no_root_squash"
            )

    def test_share_create_client_already_exists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    },
                    'nfsShare': [{
                        'id': 'NFSShare_1'
                    }]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/NFSShare_1?fields=defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0",
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                Share.AlreadyExists,
                driver.share.create,
                "/test_fs",
                "1.2.3.0/24",
                "rw,no_root_squash"
            )

    def test_share_create_client_already_exists_wild(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=nfsShare,storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    },
                    'nfsShare': [{
                        'id': 'NFSShare_1'
                    }]
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/NFSShare_1?fields=defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0",
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                Share.AlreadyExists,
                driver.share.create,
                "/test_fs",
                "*",
                "ro"
            )

    def test_share_delete_remove(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:vx/test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 0,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.4.0/255.255.255.0",
                    "filesystem": {
                        "id":"fs_1",
                        "storageResource": {
                            "id":"res_1"
                        }
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareDelete': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        }
                    }
                ]
            },
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            shares = driver.share.delete("/vx/test_fs", "1.2.4.0/24")

    def test_share_delete_modify(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:vx/test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0,1.2.4.0/255.255.255.0",
                    "filesystem": {
                        "id":"fs_1",
                        "storageResource": {
                            "id":"res_1"
                        }
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareModify': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        },
                        'nfsShareParameters': {
                            'readWriteRootHostsString': '1.2.3.0/255.255.255.0'
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            shares = driver.share.delete("/vx/test_fs", "1.2.4.0/24")

    def test_share_delete_remove_wild(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"",
                    "filesystem": {
                        "id":"fs_1",
                        "storageResource": {
                            "id":"res_1"
                        }
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareDelete': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        }
                    }
                ]
            },
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            shares = driver.share.delete("/test_fs", "*")

    def test_share_delete_modify_wild(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 1,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.3.0/255.255.255.0,1.2.4.0/255.255.255.0",
                    "filesystem": {
                        "id":"fs_1",
                        "storageResource": {
                            "id":"res_1"
                        }
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/storageResource/res_1/action/modifyFilesystem',
            {
                'nfsShareModify': [
                    {
                        'nfsShare': {
                            'id': 'NFSShare_1'
                        },
                        'nfsShareParameters': {
                            'defaultAccess': 0
                        }
                    }
                ]
            },
            200,
            {
                'content': {
                    'storageResource': {
                        'id': 'sv_1'
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            shares = driver.share.delete("/test_fs", "*")

    def test_share_delete_notexist(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DeletionException,
                 driver.share.delete,
                 "/test_fs",
                 "1.2.4.0/24"
            )

    def test_share_delete_badclient(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nfsShare/name:test_fs?fields=filesystem.storageResource,defaultAccess,readOnlyHostsString,readWriteHostsString,readOnlyRootHostsString,readWriteRootHostsString',
            None,
            200,
            {
                'content': {
                    'id': 'NFSShare_1',
                    'defaultAccess': 0,
                    "readOnlyHostsString":"",
                    "readWriteHostsString":"",
                    "readOnlyRootHostsString":"",
                    "readWriteRootHostsString":"1.2.4.0/255.255.255.0",
                    "filesystem": {
                        "id":"fs_1",
                        "storageResource": {
                            "id":"res_1"
                        }
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DeletionException,
                 driver.share.delete,
                 "/test_fs",
                 "1.2.3.0/24"
            )

    def test_snapshot_list(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/snap/instances?filter=storageResource.type==1&fields=name,storageResource.name,creationTime',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            "id":"1",
                            "name":"test_fs_snap1",
                            "storageResource": {
                                "id":"res_1",
                                "name":"test_fs"
                            },
                            "creationTime":"2022-07-25T08:20:30.171Z"
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            results = driver.snapshot.list()
            self.assertTrue(len(results) == 1)
            pprint.pprint(results)
            self.assertEqual(results[0].name, "test_fs_snap1")

    def test_snapshot_create(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/types/snap/instances',
            {
                'storageResource': {
                    'id': 'res_1'
                },
                'name': 'test_fs_snap1'
            },
            201,
            None
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            result = driver.snapshot.create("test_fs_snap1", "test_fs", None)
            self.assertEqual(result.name, "test_fs_snap1")

    def test_snapshot_create_badfs(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.snapshot.create,
                "test_fs_snap1",
                "test_fs",
                None
            )

    def test_snapshot_restore(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/snap/name:test_fs_snap1?fields=id',
            None,
            200,
            {
                'content': {
                    'id': '1',
                }
            }
        )
        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/snap/1/action/restore',
            None,
            200,
            {
                'content': {
                    'backup': {
                        'id': 2
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/snap/2',
            None,
            204,
            None
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.snapshot.restore("test_fs_snap1", "test_fs")

    def test_snapshot_rollback_info(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/snap/name:test_rollbackinfo_snap?fields=name,creationTime,size',
            None,
            200,
            {
                'content': {
                    'name': 'test_snap',
                    'creationTime': '2021/11/12 09:19',
                    'size': '192K'
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            result = driver.snapshot.rollbackinfo("test_rollbackinfo_snap")
            self.assertTrue('test_snap' in result[1])

    def test_snapshot_rollback_info_notexists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/snap/name:test_invalid_snap?fields=name,creationTime,size',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.snapshot.rollbackinfo,
                "test_invalid_snap"
            )

    def test_snapshot_restore_badfs(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.snapshot.restore,
                "test_fs_snap1",
                "test_fs"
            )

    def test_snapshot_restore_notexists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/snap/name:test_fs_snap1?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US':'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.snapshot.restore,
                "test_fs_snap1",
                "test_fs"
            )

    def test_snapshot_delete(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/filesystem/name:test_fs?fields=storageResource',
            None,
            200,
            {
                'content': {
                    'id': 'fs_1',
                    'storageResource': {
                        'id': 'res_1'
                    }
                }
            }
        )
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/snap/name:test_fs_snap1?fields=id',
            None,
            200,
            {
                'content': {
                    'id': '1',
                }
            }
        )
        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/snap/1',
            None,
            204,
            None
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.snapshot.delete("test_fs_snap1", "test_fs")

    def test_cache_list(self):
        self.initMock()
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            cache_list = driver.cache.list()
            self.assertTrue(len(cache_list) == 0)

    def test_not_implemented(self):
        self.initMock()
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                NotImplementedError,
                driver.disk.list
            )
            self.assertRaises(
                NotImplementedError,
                driver.disk.create
            )
            self.assertRaises(
                NotImplementedError,
                driver.disk.delete
            )
            self.assertRaises(
                NotImplementedError,
                driver.pool.list
            )
            self.assertRaises(
                NotImplementedError,
                driver.pool.create
            )
            self.assertRaises(
                NotImplementedError,
                driver.pool.delete
            )
            self.assertRaises(
                NotImplementedError,
                driver.cache.create,
                None,
                None,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.cache.delete,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.cache.resize,
                None,
                None,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.cache.get_related_snapshots,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.execute,
                None,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.execute_cmd,
                None,
                None
            )
            self.assertRaises(
                NotImplementedError,
                driver.verify_discovery
            )



    def assertIsInstance(self, obj, cls):
        """
        Implementation of assertIsInstance (which is available in 2.7)
        """
        yes = isinstance(obj, cls)
        if not yes:
            self.fail("%s is type %s, should be %s" % (obj, type(obj), cls))


    def setUp(self):
        self.spa = "1.2.3.4"
        self.spb = "1.2.3.5"
        self.adminuser = "admin"
        self.adminpasswd = "shroot12"
        self.scope = "global"

        self.logger = logging.getLogger("unityxttest")
        if not TestUnityXT.logging_setup:
            self.logger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(ch)
            TestUnityXT.logging_setup = True

        UnityRESTMocker.setup("hostname")

    def initMock(self):
        UnityRESTMocker.reset()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/loginSessionInfo/instances',
            None,
            200,
            None
        )

    def test_nas_server_create(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spa'
                },
                'name': 'enm1071_vs_enm_1',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.8',
                'ipPort': {
                    'id': 'spa_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_1'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nfsServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'nfsv3Enabled': False,
                'nfsv4Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spa',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileNDMPServer/instances?fields=id,nasServer,username',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileNDMPServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'password': 'P@ssw0rd12'
            },
            200,
            {
                'content': {
                    'id': 'ndmp_1'
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nscreate = driver.nasserver.create(
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_failback_successful(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spa'
                },
                'name': 'enm1071_vs_enm_1',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.8',
                'ipPort': {
                    'id': 'spa_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_1'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nfsServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'nfsv3Enabled': False,
                'nfsv4Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spa',
                    'homeSP': 'spb'
                }
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/system/0/action/failback?timeout=2',
            None,
            200,
            None
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spa',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileNDMPServer/instances?fields=id,nasServer,username',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileNDMPServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'password': 'P@ssw0rd12'
            },
            200,
            {
                'content': {
                    'id': 'ndmp_1'
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nscreate = driver.nasserver.create(
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    @patch("naslib.unityxt.resources.NasServerResource.sp_check_attempts", new=1)
    def test_nas_server_create_failback_unsuccessful(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spa'
                },
                'name': 'enm1071_vs_enm_1',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.8',
                'ipPort': {
                    'id': 'spa_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_1'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nfsServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'nfsv3Enabled': False,
                'nfsv4Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spb',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/system/0/action/failback?timeout=2',
            None,
            200,
            None
            )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spb',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileNDMPServer/instances?fields=id,nasServer,username',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileNDMPServer/instances',
            {
                'nasServer': {
                    'id': u'nas_1'
                },
                'password': 'P@ssw0rd12'
            },
            200,
            {
                'content': {
                    'id': 'ndmp_1'
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_missing_network_param(self):
        self.initMock()

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "a,2",
                "spb,5.6.7.9,255.255.254.0",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_fsn_exists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spb_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            200,
            {
                'content': {
                    'id': 'spb_fsn_ocp_0_0',
                    'primaryPort': {
                        'id': 'spb_ocp_0_eth0',
                    },
                    'secondaryPorts': [
                        {
                            'id': 'spb_ocp_0_eth2'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spb?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spb'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spb'
                },
                'name': 'enm1071_vs_enm_2',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_2'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.9',
                'ipPort': {
                    'id': 'spb_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_2'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_2'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nfsServer/instances',
            {
                'nasServer': {
                    'id': u'nas_2'
                },
                'nfsv3Enabled': False,
                'nfsv4Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_2'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_2?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spa',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileNDMPServer/instances?fields=id,nasServer,username',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileNDMPServer/instances',
            {
                'nasServer': {
                    'id': u'nas_2'
                },
                'password': 'P@ssw0rd12'
            },
            200,
            {
                'content': {
                    'id': 'ndmp_2'
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nscreate = driver.nasserver.create(
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_missing_port(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_non_numeric_port(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'spa_fsn_ocp_0_0',
                            'primaryPort': {
                                'id': 'spa_ocp_0_eth0',
                            },
                            'secondaryPorts': [
                                {
                                    'id': 'spa_ocp_0_eth2'
                                }
                            ],
                            'storageProcessor': {
                                'id': 'spa'
                            }
                        }
                    },
                    {
                        'content': {
                            'id': 'spb_fsn_ocp_0_0',
                            'primaryPort': {
                                'id': 'spb_ocp_0_eth0',
                            },
                            'secondaryPorts': [
                                {
                                    'id': 'spb_ocp_0_eth2'
                                }
                            ],
                            'storageProcessor': {
                                'id': 'spb'
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "a,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_port_is_down(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': False
                }
            }
        )


        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_fsn_exists_wrong_ports(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spb_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            200,
            {
                'content': {
                    'id': 'spb_fsn_ocp_0_0',
                    'primaryPort': {
                        'id': 'spb_ocp_0_eth0',
                    },
                    'secondaryPorts': [
                        {
                            'id': 'spb_ocp_0_eth3'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_missing_pool(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_missing_sp(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_exists_wrong_sp(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spb'
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_exists_wrong_pool(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_2',
                                'name': 'ENM1072'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_fsn_ns_fi_nfs_ndmp_exists(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spb_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            200,
            {
                'content': {
                    'id': 'spb_fsn_ocp_0_0',
                    'primaryPort': {
                        'id': 'spb_ocp_0_eth0',
                    },
                    'secondaryPorts': [
                        {
                            'id': 'spb_ocp_0_eth2'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spb?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spb'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    },
                    {
                        'content': {
                            'id': 'nas_2',
                            'name': 'enm1071_vs_enm_2',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spb'
                            }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "if_1",
                            "ipAddress": "5.6.7.8",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.7.1",
                            "nasServer": {
                                "id": "nas_1"
                            },
                            "ipPort": {
                                "id": "spa_fsn_ocp_0_0"
                            }
                        }
                    },
                    {
                        "content": {
                            "id": "if_2",
                            "ipAddress": "5.6.7.9",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.7.1",
                            "nasServer": {
                                "id": "nas_2"
                            },
                            "ipPort": {
                                "id": "spb_fsn_ocp_0_0"
                            }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "nfs_1",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_1"
                             }
                        }
                    },
                    {
                        "content": {
                            "id": "nfs_2",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_2"
                             }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_2?fields=currentSP,homeSP',
            None,
            200,
            {
                'content': {
                    'currentSP': 'spa',
                    'homeSP': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileNDMPServer/instances?fields=id,nasServer,username',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'ndmp_1',
                            'nasServer': {
                                'id': 'nas_1'
                            },
                            'username': 'admin'
                        },
                        'content': {
                            'id': 'ndmp_2',
                            'nasServer': {
                                'id': 'nas_2'
                            },
                            'username': 'admin'
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/fileNDMPServer/ndmp_2/action/modify',
            {
                'password': 'P@ssw0rd12'
            },
            200,
            {
                'content': {
                    'id': 'ndmp_2'
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nscreate = driver.nasserver.create(
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_wrong_gateway(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spb_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            200,
            {
                'content': {
                    'id': 'spb_fsn_ocp_0_0',
                    'primaryPort': {
                        'id': 'spb_ocp_0_eth0',
                    },
                    'secondaryPorts': [
                        {
                            'id': 'spb_ocp_0_eth2'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spb?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spb'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spb'
                },
                'name': 'enm1071_vs_enm_2',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_2'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "if_1",
                            "ipAddress": "5.6.7.8",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.6.1",
                            "nasServer": {
                                "id": "nas_1"
                            },
                            "ipPort": {
                                "id": "spa_fsn_ocp_0_0"
                            }
                        }
                    },
                    {
                        "content": {
                            "id": "if_2",
                            "ipAddress": "5.6.7.9",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.6.1",
                            "nasServer": {
                                "id": "nas_2"
                            },
                            "ipPort": {
                                "id": "spb_fsn_ocp_0_0"
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_fi_wrong_server(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spb_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spb_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spb_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            200,
            {
                'content': {
                    'id': 'spb_fsn_ocp_0_0',
                    'primaryPort': {
                        'id': 'spb_ocp_0_eth0',
                    },
                    'secondaryPorts': [
                        {
                            'id': 'spb_ocp_0_eth2'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spb?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spb'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spb'
                },
                'name': 'enm1071_vs_enm_2',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_2'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "if_1",
                            "ipAddress": "5.6.7.8",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.7.1",
                            "nasServer": {
                                "id": "nas_1"
                            },
                            "ipPort": {
                                "id": "spa_fsn_ocp_0_0"
                            }
                        }
                    },
                    {
                        "content": {
                            "id": "if_2",
                            "ipAddress": "5.6.7.9",
                            "netmask": "255.255.254.0",
                            "gateway": "5.6.7.1",
                            "nasServer": {
                                "id": "nas_4"
                            },
                            "ipPort": {
                                "id": "spb_fsn_ocp_0_0"
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_2",
                "ENM1071",
                "0,2",
                "spb,5.6.7.9,255.255.254.0,5.6.7.1",
                "nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_create_invalid_protocol(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spa'
                },
                'name': 'enm1071_vs_enm_1',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.8',
                'ipPort': {
                    'id': 'spa_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_1'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': []
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv5",
                "P@ssw0rd12"
            )

    def test_nas_server_create_nfs_exists_wrong_protocol(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth0?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth0',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/ipPort/spa_ocp_0_eth2?fields=isLinkUp',
            None,
            200,
            {
                'content': {
                    'id': 'spa_ocp_0_eth2',
                    'isLinkUp': True
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0?fields=id,primaryPort,secondaryPorts',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fsnPort/instances?fields=id,primaryPort,secondaryPorts,storageProcessor',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fsnPort/instances',
            {
                'primaryPort': {
                    'id': 'spa_ocp_0_eth0'
                },
                'secondaryPorts': [
                    {
                        'id': 'spa_ocp_0_eth2'
                    }
                ]
            },
            200,
            {
                'content': {
                    'id': 'spa_fsn_ocp_0_0'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/pool/name:ENM1071?fields=id',
            None,
            200,
            {
                'content': {
                    'id': 'pool_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/storageProcessor/spa?fields=',
            None,
            200,
            {
                'content': {
                    'id': 'spa'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=id,pool,homeSP,name',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/nasServer/instances',
            {
                'homeSP': {
                    u'id': u'spa'
                },
                'name': 'enm1071_vs_enm_1',
                'pool': {
                    'id': u'pool_1'
                }
            },
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/fileInterface/instances?fields=id,nasServer,ipPort,ipAddress,netmask,gateway',
            None,
            200,
            {
                'entries': []
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/types/fileInterface/instances',
            {
                'gateway': '5.6.7.1',
                'ipAddress': '5.6.7.8',
                'ipPort': {
                    'id': 'spa_fsn_ocp_0_0'
                },
                'nasServer': {
                    'id': 'nas_1'
                },
                'netmask': '255.255.254.0'
            },
            200,
            {
                'content': {
                    'id': 'if_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "nfs_1",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_1"
                             }
                        }
                    },
                    {
                        "content": {
                            "id": "nfs_2",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_2"
                             }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                CreationException,
                driver.nasserver.create,
                "enm1071_vs_enm_1",
                "ENM1071",
                "0,2",
                "spa,5.6.7.8,255.255.254.0,5.6.7.1",
                "nfsv3,nfsv4",
                "P@ssw0rd12"
            )

    def test_nas_server_delete(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=id,fileInterface.ipPort',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                    'fileInterface': [
                        {
                            'id': 'if_1',
                            'ipPort': {
                                'id': 'spa_fsn_ocp_0_0'
                            }
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/nasServer/nas_1',
            None,
            204,
            None
        )

        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/fsnPort/spa_fsn_ocp_0_0',
            None,
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nsdelete = driver.nasserver.delete("enm1071_vs_enm_1")

    def test_nas_server_delete_not_exist(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=id,fileInterface.ipPort',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nsdelete = driver.nasserver.delete("enm1071_vs_enm_1")
            self.assertTrue(nsdelete is None)

    def test_nas_server_delete_no_fsn(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=id,fileInterface.ipPort',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                    'fileInterface': [
                        {
                            'id': 'if_1'
                        }
                    ]
                }
            }
        )

        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/nasServer/nas_1',
            None,
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nsdelete = driver.nasserver.delete("enm1071_vs_enm_1")

    def test_nas_server_delete_no_fi(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=id,fileInterface.ipPort',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'DELETE',
            '/api/instances/nasServer/nas_1',
            None,
            204,
            None
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nsdelete = driver.nasserver.delete("enm1071_vs_enm_1")

    def test_nas_server_list(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nasServer/instances?fields=name,pool.name,homeSP.id',
            None,
            200,
            {
                'entries': [
                    {
                        'content': {
                            'id': 'nas_1',
                            'name': 'enm1071_vs_enm_1',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spa'
                            }
                        }
                    },
                    {
                        'content': {
                            'id': 'nas_2',
                            'name': 'enm1071_vs_enm_2',
                            'pool': {
                                'id': 'pool_1',
                                'name': 'ENM1071'
                            },
                            'homeSP': {
                                'id': 'spb'
                            }
                        }
                    }
                ]
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nasservers = driver.nasserver.list()
            self.assertTrue(len(nasservers) == 2)
            pprint.pprint(nasservers)
            pprint.pprint(nasservers[0].name)
            self.assertEqual(nasservers[0].name, "enm1071_vs_enm_1")
            self.assertEqual(nasservers[0].pool.name, "ENM1071")
            self.assertEqual(nasservers[0].homesp, "spa")
            self.assertEqual(nasservers[1].name, "enm1071_vs_enm_2")
            self.assertEqual(nasservers[1].pool.name, "ENM1071")
            self.assertEqual(nasservers[1].homesp, "spb")

    def test_nas_server_get_nasserver_details(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:enm1071_vs_enm_1?fields=id,name,health,homeSP,currentSP,pool.name,sizeAllocated,fileSpaceUsed,fileInterface.ipPort,fileInterface.ipAddress,fileInterface.netmask,fileInterface.gateway,filesystems,nfsServer.nfsv3Enabled,nfsServer.nfsv4Enabled',
            None,
            200,
            {
                'content': {
                    'id': 'nas_1',
                    'name': 'enm1071_vs_enm_1',
                    'health': {
                        'value': 5,
                        'descriptionIds': ["ALRT_COMPONENT_OK"],
                        "descriptions": ["The component is operating normally. No action is required."]
                    },
                    'sizeAllocated': 2952790016,
                    'fileSpaceUsed': 2458402816,
                    'homeSP': {
                        'id': 'spa'
                    },
                    'currentSP': {
                        'id': 'spa'
                    },
                    'pool': {
                        'id': 'pool_1',
                        'name':'ENM1071'
                    },
                    'fileInterface': [
                        {
                            'id': 'if_1',
                            'ipAddress': '5.6.7.8',
                            'netmask': '255.255.254.0',
                            'gateway': '5.6.7.1',
                            'ipPort': {
                                'id': 'spa_fsn_ocp_0_0'
                            }
                        }
                    ],
                    'nfsServer': {
                        'id': 'nfs_1',
                        'nfsv3Enabled': False,
                        'nfsv4Enabled': True
                    }
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            nasserver = driver.nasserver.get_nasserver_details("enm1071_vs_enm_1")
            pprint.pprint(nasserver)
            pprint.pprint(nasserver['name'])
            self.assertEqual(nasserver['name'], "enm1071_vs_enm_1")
            self.assertEqual(nasserver['health']['value'], 5)
            self.assertEqual(nasserver['homeSP']['id'], "spa")
            self.assertEqual(nasserver['fileInterface'][0]['ipPort']['id'], "spa_fsn_ocp_0_0")
            self.assertEqual(nasserver['nfsServer']['nfsv4Enabled'], True)

    def test_nas_server_get_nasserver_details_fail(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/instances/nasServer/name:does_not_exist?fields=id,name,health,homeSP,currentSP,pool.name,sizeAllocated,fileSpaceUsed,fileInterface.ipPort,fileInterface.ipAddress,fileInterface.netmask,fileInterface.gateway,filesystems,nfsServer.nfsv3Enabled,nfsServer.nfsv4Enabled',
            None,
            404,
            {
                'error': {
                    'errorCode': 131149829,
                    'httpStatusCode': 404,
                    'messages': [
                        {
                            'en-US': 'The requested resource does not exist. (Error Code:0x7d13005)'
                        }
                    ]
                }
            }
        )

        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            self.assertRaises(
                DoesNotExist,
                driver.nasserver.get_nasserver_details,
                "does_not_exist"
            )

    def test_change_sharing_protocol(self):
        self.initMock()
        UnityRESTMocker.add_request(
            'GET',
            '/api/types/nfsServer/instances?fields=id,nasServer,nfsv3Enabled,nfsv4Enabled',
            None,
            200,
            {
                'entries': [
                    {
                        "content": {
                            "id": "nfs_1",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_1"
                             }
                        }
                    },
                    {
                        "content": {
                            "id": "nfs_2",
                            "nfsv3Enabled": False,
                            "nfsv4Enabled": True,
                            "nasServer": {
                                "id": "nas_2"
                             }
                        }
                    }
                ]
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/nfsServer/nfs_1/action/modify',
            {
                'nfsv4Enabled': True,
                'nfsv3Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_1'
                }
            }
        )

        UnityRESTMocker.add_request(
            'POST',
            '/api/instances/nfsServer/nfs_2/action/modify',
            {
                'nfsv4Enabled': True,
                'nfsv3Enabled': True
            },
            200,
            {
                'content': {
                    'id': 'nfs_2'
                }
            }
        )
        with NasConnection("hostname", "user", "password", nas_type="unityxt") as driver:
            driver.nasserver.change_sharing_protocol("nfsv3,nfsv4")

    @patch('logging.Logger.log')
    @patch('naslib.unityxt.unityrest.requests.Session.request')
    def test_three_request_exceptions(self, mock_request, mock_logger):
        mock_request.side_effect = [
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectionError
        ]
        logger = logging.getLogger('test.logger')
        UnityREST.set_mock(None)
        unityrest = UnityREST(logger)
        with patch.object(unityrest, '_UnityREST__ip_address', '1.1.1.1'):
            self.assertRaises(NasConnectionException, unityrest.request, '/test/endpoint')
            mock_logger.assert_called_with(logging.INFO, 'request: attempts remaining=0')

    @patch('logging.Logger.log')
    @patch('naslib.unityxt.unityrest.requests.Session.request')
    @patch('naslib.unityxt.unityrest.requests.Response')
    def test_two_request_exceptions(self, mock_response, mock_request, mock_logger):
        mock_request.side_effect = [
            requests.exceptions.ConnectionError('Error Message'),
            requests.exceptions.ConnectionError('Error Message'),
            mock_response
        ]

        logger = logging.getLogger('test.logger')
        UnityREST.set_mock(None)
        unityrest = UnityREST(logger)
        with patch.object(unityrest, '_UnityREST__ip_address', '1.1.1.1'):
            unityrest.request('/test/endpoint')
            mock_logger.assert_any_call(logging.INFO, 'request: attempts remaining=1')
            mock_logger.assert_any_call(logging.INFO, 'request: exception=Error Message endpoint=/test/endpoint')
            mock_logger.assert_any_call(logging.INFO, 'request: delay for 3 seconds')