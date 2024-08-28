import re
import mock
from test_sfs import TestSfsDb
from naslib.drivers.va.resources import FileSystemResource, ShareResource
from naslib.nasmock.connection import NasConnectionMock
from naslib.nasexceptions import NasIncompleteParsedInformation, \
    NasException, NasUnexpectedOutputException


class TestVaDb(TestSfsDb):
    def setUp(self):
        self.driver_name = 'Va'
        self.type = 'ACCESS'
        self.extra_hard_coded_option = "nordirplus"
        self.incomplete_cache_out = \
"""
CACHE NAME           TOTAL(Mb)       USED(Mb) (%)      AVAIL(Mb) (%)   SDCNT
==========           =========       ===============   ==============  =====
CI15_cache1                 25          4 (16.00)         21 (84.00)       1
68Cache1                    40          4 (10.00)         36 (90.00)       1
ST51-cache                   -          -    (-)          -      (-)       -
105cache1                 1104          5  (0.00)       1099 (99.00)       0
ST66_cashe                 360          5  (1.00)        355 (98.00)       2
"""

    def test_empty_pool_parsing(self):
        mock_args = "10.44.86.226", "support", "support"
        err = None

        # testing empty pool issue
        vxprint_fs_out = """
TY NAME         ASSOC        KSTATE   LENGTH   PLOFFS   STATE    TUTIL0  PUTIL0
vt CI42-managed-fs2 -        ENABLED  -        -        ACTIVE   -       -
v  CI42-managed-fs2_tier1 CI42-managed-fs2 ENABLED 102400 - ACTIVE -     -
pl CI42-managed-fs2_tier1-01 CI42-managed-fs2_tier1 ENABLED 102400 - ACTIVE - -
"""
#sd emc_clariion0_110-07       CI42-managed-fs2_tier1-01 ENABLED 102400 0 -     -       -

        output = (re.compile(r"^vxprint -hrAF sd:'%type %name %assoc "
            r"%kstate %len %column_pl_offset %state %tutil0 %putil0 "
            r"%device'\s+CI42-managed-fs2"), vxprint_fs_out, "")
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.fs_get_max_number_of_attempts = 1
                s.filesystem.fs_get_delay_between_attemps = 1
                fs = s.filesystem.get('CI42-managed-fs2')
                _ = fs.pool
        except NasException as err:
            pass
        self.assertTrue(isinstance(err, NasIncompleteParsedInformation))
        self.assertTrue("empty values for the pool name" in str(err))
        self.assertTrue(hasattr(err, 'parsed_data'))

    def test_invalid_pool_parsing(self):
        mock_args = "10.44.86.226", "support", "support"

        vxprint_fs_out = """
TY NAME         ASSOC        KSTATE   LENGTH   PLOFFS   STATE    TUTIL0  PUTIL0
vt CI42-managed-fs2 -        ENABLED  -        -        ACTIVE   -       -
v  CI42-managed-fs2_tier1 CI42-managed-fs2 ENABLED 102400 - ACTIVE -     -
pl CI42-managed-fs2_tier1-01 CI42-managed-fs2_tier1 ENABLED 102400 - ACTIVE - -
sd Invalid Disk       CI42-managed-fs2_tier1-01 ENABLED 102400 0 -     -       - sda
"""
        output = (re.compile(r"^vxprint -hrAF sd:'%type %name %assoc "
            r"%kstate %len %column_pl_offset %state %tutil0 %putil0 "
            r"%device'\s+CI42-managed-fs2"), vxprint_fs_out, "")
        err = None
        try:
            with NasConnectionMock(*mock_args, driver_name=self.driver_name, stash=True, output=output) as s:
                s.filesystem.fs_get_max_number_of_attempts = 1
                s.filesystem.fs_get_delay_between_attemps = 1
                fs = s.filesystem.get('CI42-managed-fs2')
                _ = fs.pool
        except Exception as err:
            pass

        self.assertTrue(isinstance(err, NasIncompleteParsedInformation))

    def test_p_build_shares_list(self):
        mock_share = ShareResource("nas")
        valid_line = ["/vx/CIcdb-managed-fs2 192.168.0.0/16", "(no_wdelay,no_root_squash,rw,nordirplus)", "/vx/ossrc1-file_system5 * (rw,no_root_squash,nordirplus)"]
        obj_list = ShareResource._build_shares_list(mock_share, valid_line, "")
        self.assertTrue(obj_list != [])

    def test_n_build_shares_list(self):
        mock_share = ShareResource("nas")
        not_valid_line = "/fs/file_system5 * (rw,no_root_squash,nordirplus) not valid"
        self.assertRaises(NasUnexpectedOutputException, ShareResource._build_shares_list, mock_share, not_valid_line, "")

    @mock.patch('naslib.drivers.sfs.resources.FileSystemResource._properties')
    @mock.patch('naslib.drivers.va.resources.FileSystemResource.vtask_list')
    def test_va74_p_is_restore_running(self, vtask_list, _properties):
        _properties.return_value = {}
        vtask_list.return_value = {"": ['PTID', 'TYPE/STATE', 'PCT', 'PROGRESS'], "1": ['-', 'SNAPSYNC/R', '33.45%', '0/41943040/14031488', 'SNAPSYNC', 'some_fs_tier1', 'sfsdg']}
        filesystem = 'Int110-storadm-snap'
        mock_fs = FileSystemResource("nas")
        result = FileSystemResource.is_restore_running(mock_fs, filesystem)
        self.assertTrue(result)

    @mock.patch('naslib.drivers.sfs.resources.FileSystemResource._properties')
    @mock.patch('naslib.drivers.va.resources.FileSystemResource.vtask_list')
    def test_va74_n_is_restore_running(self, vtask_list, _properties):
        _properties.return_value = {}
        vtask_list.return_value = {}
        filesystem = 'Int110-storadm-snap'
        mock_fs = FileSystemResource("nas")
        result = FileSystemResource.is_restore_running(mock_fs, filesystem)
        self.assertFalse(result)

    @mock.patch('naslib.drivers.sfs.resources.FileSystemResource._properties')
    def test_va72_p_is_restore_running(self,  _properties):
        _properties.return_value = {'Rollsync Status': {'Rollback some_fs, Tier 1': '54.88%  Start_time: Feb/15/2019/15:28:40   Work_time: 0:1:30     Remaining_time: 01:13'}}
        filesystem = 'Int110-storadm-snap'
        mock_fs = FileSystemResource("nas")
        result = FileSystemResource.is_restore_running(mock_fs, filesystem)
        self.assertTrue(result)

    @mock.patch('naslib.drivers.sfs.resources.FileSystemResource._properties')
    @mock.patch('naslib.drivers.va.resources.FileSystemResource.vtask_list')
    def test_va72_n_is_restore_running(self, vtask_list, _properties):
        _properties.return_value = {'Rollsync Status': 'Not Running'}
        vtask_list.return_value = {}
        filesystem = 'Int110-storadm-snap'
        mock_fs = FileSystemResource("nas")
        result = FileSystemResource.is_restore_running(mock_fs, filesystem)
        self.assertFalse(result)
