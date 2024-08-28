##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains generic parsers for outputs of "vx*" commands such as
"vxprint", "vxdg", "vxdisk", etc.
"""


class SfsAdminShowParser(object):
    r""" This is a parser for the output coming from SFS console command
    "admin show <USER>" like the example below:

        ammsfs> admin show user_test
        Username      : user_test
        Privileges    : Storage Administrator

    >>> o = "Username      : user_test\nPrivileges    : Storage Administrator"
    >>> parser = SfsAdminShowParser(o)
    >>> parser.parse()
    {'Username': 'user_test', 'Privileges': 'Storage Administrator'}
    """

    data_sep = ':'

    def __init__(self, output):
        """ The constructor requires only the output string.
        """
        self.output = output

    @property
    def lines(self):
        """ Retrieves non empty lines.
        """
        return [i for i in self.output.splitlines() if i.strip()]

    def parse(self):
        """ Parses the output lines and builds a dict.
        """
        data = lambda x: tuple([i.strip() for i in x.split(self.data_sep)])
        return dict([data(l) for l in self.lines])


class VxPropertiesSimpleOutputParser(object):
    """ This is a parser for some outputs coming from vx* commands that has
    a format almost like a YAML. See an output example below:

    >>> vxdisk_output = \"\"\"
    ... General Info:
    ... ===============
    ... Block Size:      1024 Bytes
    ... Version:          Version 8
    ... SFS_01:        offline
    ...
    ... Primary Tier
    ... ============
    ... Size:            1.00G
    ... Use%:            -
    ... Layout:          simple
    ... Mirrors:         -
    ... Columns:         -
    ... Stripe Unit:     0.00 K
    ... FastResync:      Enabled
    ...
    ... 1. Mirror 01:
    ... List of pools:   litp2
    ... List of disks:   sdb
    ...
    ... Defrag Status: Not Running
    ... Fullfsck Status: Not Running
    ... Resync   Status: Not Running
    ... Rollsync Status:
    ...     Rollback rogerio1, Tier 1: 83.59%  Start_time: \
Jul/15/2015/11:33:19   Work_time: 0:0:46     Remaining_time: 0:09
    ... Relayout Status: Not Running
    ... \"\"\"
    >>> parser = VxPropertiesSimpleOutputParser(vxdisk_output)
    >>> data = parser.parse()
    >>> data['Resync   Status']
    'Not Running'
    >>> data['List of pools']
    'litp2'
    """

    data_sep = ':'
    data_sep_space = ' '

    def __init__(self, output):
        """ The constructor requires only the output string.
        """
        self.output = output

    @property
    def lines(self):
        """ Retrieves non empty lines.
        """
        return [i for i in self.output.splitlines() if i.strip()]

    def parse(self):
        """ Parses the output lines and builds a dict. As some outputs of vx*
        commands are not regular, we assume two kinds of data separator like
        ":" and " ", data_sep and data_sep_space respectively.
        Each value after the separator can also be a dict, list or just
        str or int. So, for each value we use the _parse_value(value) method.

        >>> vxdg_minus_q_list_output = \"\"\"
        ... Group:     sfsdg
        ... dgid:      1359985462.17.ammsfs_01
        ... import-id: 33792.8
        ... flags:     shared
        ... version:   160
        ... alignment: 8192 (bytes)
        ... local-activation: shared-write
        ... cluster-actv-modes: ammsfs_01=sw
        ... ssb:            on
        ... autotagging:    on
        ... detach-policy: local
        ... dg-fail-policy: leave
        ... copies:    nconfig=default nlog=default
        ... config:    seqno=0.530510 permlen=51360 free=50174 templen=267
        ... config disk emc_clariion0_110 copy 1 len=51360 state=clean online
        ... config disk emc_clariion0_121 copy 1 len=51360 state=clean online
        ... log disk emc_clariion0_110 copy 1 len=4096
        ... log disk emc_clariion0_121 copy 1 len=4096
        ... \"\"\"
        >>> parser = VxPropertiesSimpleOutputParser(vxdg_minus_q_list_output)
        >>> data = parser.parse()
        >>> data['flags']
        'shared'
        >>> data['copies']
        'nconfig=default nlog=default'
        """
        data = {}
        nested_props = {}
        nested_key = None
        tier_info = "Tier Info:"
        for line in self.lines:
            if tier_info in line:
                key, value = tier_info.strip(':'),\
                        self.lines[self.lines.index(tier_info) + 2]
            elif self.data_sep in line:
                key, value = line.split(self.data_sep, 1)
            elif self.data_sep_space in line:
                key, value = line.split(self.data_sep_space, 1)
            else:
                continue
            if tier_info in key:
                data[key] = self._parse_value(value)
            if key.startswith(' '):
                nested_props[key.strip()] = self._parse_value(value)
                continue
            if nested_props:
                data[nested_key] = nested_props
                continue
            nested_props = {}
            nested_key = None
            if not value.strip():
                nested_key = key.strip()
                continue
            data[key] = self._parse_value(value)
        return data

    def _parse_value(self, value):
        """ This method is reserved for the child classes in case of any
        treatment in the value.
        """
        return value.strip()


class VxPropertiesOutputParser(VxPropertiesSimpleOutputParser):
    """ This is a parser for some outputs coming from vx* commands that has
    a format almost like a YAML. See an output example below:
    """

    key_value_sep = '='

    def _to_int(self, value):
        """ Some values may be a digit, so this method cast it to int.
        """
        return int(value) if value.isdigit() else value

    def _parse_value(self, value):
        """ Each value can be characterized as dict, list, str or int. If
        there's '=' (key_value_sep), that means that it's a key=value, so we
        can build a dict for it. Otherwise could be a list of strs or ints, in
        case of more than 1 item, or just a single str or int.
        As outputs of vx* commands are not regular unfortunately, some values
        may have both dict and item, like: "min=512 (bytes) max=1024 (blocks)",
        but it's hard to parse it and retrieve a good result. So this function
        just prioritize dict.

        >>> vxdg_minus_q_list_output = \"\"\"
        ... Group:     sfsdg
        ... flags:     shared
        ... dg-fail-policy: leave
        ... copies:    nconfig=default nlog=default
        ... config:    seqno=0.530510 permlen=51360 free=50174 templen=267
        ... \"\"\"
        >>> parser = VxPropertiesOutputParser(vxdg_minus_q_list_output)
        >>> data = parser.parse()
        >>> data['config']
        {'permlen': 51360, 'seqno': '0.530510', 'templen': 267, 'free': 50174}
        >>> data['copies']
        {'nconfig': 'default', 'nlog': 'default'}
        """
        values = value.split(',')
        if len(values) == 1:
            values = value.split()
        value_data = {}
        value_list = []
        for value in values:
            if self.key_value_sep in value:
                key, value = value.split(self.key_value_sep, 1)
                value_data[key.strip()] = self._to_int(value)
            else:
                value_list.append(self._to_int(value.strip()))
        value_list = value_list[0] if len(value_list) == 1 else value_list
        return value_data or value_list


class VxGenericListOutput(object):
    """ This is a parser for outputs coming from generic "vx*" commands that
    lists data.
    """

    def __init__(self, output, unique_key='name'):
        """ Just requires the output from a generic "vx*" command. It should
        have a list format (e.g: vxprint, vxdisk listtag, etc.).
        """
        self.output = output.strip()
        self.unique_key = unique_key
        self._header = []

    @property
    def header(self):
        """ Retrieves the header titles as a list.
        """
        if not self._header:
            header = self._get_header_line().split()
            self._header = [i.strip().lower() for i in header]
        return self._header

    def _get_header_line(self):
        """ Returns the header line information.
        """
        lines = [i.strip() for i in self.output.splitlines() if i.strip()]
        return lines[0]

    def parse(self):
        """ Parses the output from cleaned lines and builds the dict data.
        """
        data = {}
        for line in self.output.splitlines()[1:]:
            d = dict(zip(self.header, line.split()))
            data[d[self.unique_key]] = d
        return data


class VxPrintOutput(VxGenericListOutput):
    """ This is a parser for outputs coming from vxprint command that has
    a format like a table. See an output example below:

    >>> vxprint_output = \"\"\"
    ... TY NAME       ASSOC      KSTATE   LENGTH  PLOFFS  STATE  TUTIL0  PUTIL0
    ... dg nbuapp     nbuapp     -        -        -        -      -       -
    ...
    ... dm disk_1     disk_1     -        9755774656 -      -      -       -
    ... dm disk_2     disk_2     -        76171777984 -     -      -       -
    ...
    ... v  advol      fsgen      ENABLED  1560281088 -      ACTIVE -       -
    ... pl advol-01   advol      ENABLED  1560281088 -      ACTIVE -       -
    ... sd disk_1-02  advol-01   ENABLED  1560281088 0      -      -       -
    ...
    ... v  catvol     fsgen      ENABLED  1951154176 -      ACTIVE -       -
    ... pl catvol-01  catvol     ENABLED  1951154176 -      ACTIVE -       -
    ... sd disk_1-01  catvol-01  ENABLED  2097152  0        -      -       -
    ... sd disk_1-03  catvol-01  ENABLED  1949057024 2097152 -     -       -
    ...
    ... v  pdvol      fsgen      ENABLED  6243221504 -      ACTIVE -       -
    ... pl pdvol-01   pdvol      ENABLED  6243221504 -      ACTIVE -       -
    ... sd disk_1-04  pdvol-01   ENABLED  6243221504 0      -      -       -
    ... \"\"\"
    >>> parser = VxPrintOutput(vxprint_output)
    >>> parser.header
    ['ty', 'name', 'assoc', 'kstate', 'length', 'ploffs', 'state', 'tutil0', \
'putil0']
    >>> data = parser.parse()
    >>> data['advol']
    {'sd': [{'kstate': 'ENABLED', 'name': 'disk_1-02', 'ty': 'sd', 'state': \
'-', 'length': '1560281088', 'assoc': 'advol-01', 'tutil0': '-', 'putil0': \
'-', 'ploffs': '0'}], 'pl': {'kstate': 'ENABLED', 'name': 'advol-01', 'ty': \
'pl', 'state': 'ACTIVE', 'length': '1560281088', 'assoc': 'advol', 'tutil0': \
'-', 'putil0': '-', 'ploffs': '-'}, 'v': {'kstate': 'ENABLED', 'name': \
'advol', 'ty': 'v', 'state': 'ACTIVE', 'length': '1560281088', 'assoc': \
'fsgen', 'tutil0': '-', 'putil0': '-', 'ploffs': '-'}}

    """

    def _get_header_line(self):
        """ Returns the header line information.
        """
        lines = [i.strip() for i in self.output.splitlines() if i.strip()]
        header_line = None
        for line in lines:
            if line.startswith('TY'):
                header_line = line
                break
        return header_line

    @property
    def blocks(self):
        """ Retrieves a list of information blocks extracted from the "vxprint"
        output.
        """
        lines = [i.strip() for i in self.output.splitlines()]
        header_line = self._get_header_line()
        if not header_line:
            return []
        index = lines.index(header_line) + 1
        return [i.strip() for i in '\n'.join(lines[index:]).split('\n\n')
                          if i.strip()]

    def parse(self):
        """ Parses the output from cleaned lines and builds the dict data.
        Each key of the dict correspond to the NAME of the resource that could
        be a TY (type) disk, group, plex, volume, etc. Each value for a key
        is a dict containing the whole line information in the table.

        As an example, a block entry of a "vxprint" output command may have the
        following lines:

        vt SFS_s -   ENABLED  -        -        ACTIVE   -       -
        v  SFS_s_tier1 SFS_s ENABLED 204800 - ACTIVE -   -
        pl SFS_s_tier1-01 SFS_s_tier1 ENABLED 204800 - ACTIVE - -
        sd emc_clariion0_110-88 SFS_s_tier1-01 ENABLED 32240 0 - -     -
        sd emc_clariion0_110-91 SFS_s_tier1-01 ENABLED 98304 32240 - - -
        sd emc_clariion0_110-92 SFS_s_tier1-01 ENABLED 74256 130544 - - -
        dc SFS_s_tier1_dco SFS_s_tier1 - - - -       -       -
        v  SFS_s_tier1_dcl gen ENABLED 544   -        ACTIVE   -       -
        pl SFS_s_tier1_dcl-01 SFS_s_tier1_dcl ENABLED 544 - ACTIVE - -
        sd emc_clariion0_121-05 SFS_s_tier1_dcl-01 ENABLED 544 0 - -   -
        pl SFS_s_tier1_dcl-02 SFS_s_tier1_dcl ENABLED 544 - ACTIVE - -
        sd emc_clariion0_110-59 SFS_s_tier1_dcl-02 ENABLED 544 0 - -   -

        Volume data is considered taking the lines from the beginning till the
        line that starts with "dc". From the "dc" line, the "data change" is
        considered until the end.

        The "sd" entry can be multiple, so the data extracted will be a list of
        "sd's".

        Thus data will be separated as follows:

        * Volume data:
        vt SFS_s -   ENABLED  -        -        ACTIVE   -       -
        v  SFS_s_tier1 SFS_s ENABLED 204800 - ACTIVE -   -
        pl SFS_s_tier1-01 SFS_s_tier1 ENABLED 204800 - ACTIVE - -
        (list of sds) [
            sd emc_clariion0_110-88 SFS_s_tier1-01 ENABLED 32240 0 - -     -
            sd emc_clariion0_110-91 SFS_s_tier1-01 ENABLED 98304 32240 - - -
            sd emc_clariion0_110-92 SFS_s_tier1-01 ENABLED 74256 130544 - - -
           ]

        * DC data:
        dc SFS_s_tier1_dco SFS_s_tier1 - - - -       -       -
        v  SFS_s_tier1_dcl gen ENABLED 544   -        ACTIVE   -       -
        pl SFS_s_tier1_dcl-01 SFS_s_tier1_dcl ENABLED 544 - ACTIVE - -
        sd emc_clariion0_121-05 SFS_s_tier1_dcl-01 ENABLED 544 0 - -   -
        pl SFS_s_tier1_dcl-02 SFS_s_tier1_dcl ENABLED 544 - ACTIVE - -
        sd emc_clariion0_110-59 SFS_s_tier1_dcl-02 ENABLED 544 0 - -   -

        """
        data = {}
        for block in self.blocks:
            lines = [i.strip() for i in block.splitlines() if i.strip()]
            first_line = dict(zip(self.header, lines[0].split()))
            name = first_line['name']
            block_data = {}
            data_dict = block_data
            for line in lines:
                values = line.split()
                if values[0] == 'sd':
                    # sd type will have an extra columna with the device
                    values_dict = dict(zip(self.header + ['device'], values))
                    # because it can can have multiple sds
                    data_dict.setdefault(values[0], [])
                    data_dict[values[0]].append(values_dict)
                else:
                    values_dict = dict(zip(self.header, values))
                    if values[0] == 'dc':
                        # dc entries has its own values
                        block_data['dc'] = {}
                        data_dict = block_data['dc']
                    data_dict[values[0]] = values_dict
            data[name] = block_data
        return data
