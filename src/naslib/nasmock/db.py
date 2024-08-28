##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the base class for the MockDb. This class represents
the global data mocked from a NAS Server.
"""

import inspect
import os
import simplejson
from abc import ABCMeta

from ..ssh import SSHClient
from .basedbresource import MockDbResourceBase
from .mockexceptions import MockException


def register_db_resources(*args):
    """ Class decorator that dynamically sets the 6 DB resources as a list in
    the _resources_db attribute into MockDb class.

    >>> err = ''
    >>> try:
    ...     @register_db_resources()
    ...     class Anyclass():
    ...         pass
    ... except Exception, err:
    ...     pass
    ...
    >>> err
    MockException('The class Anyclass must be a sub class of MockDb',)
    >>> err = ''
    >>> try:
    ...     @register_db_resources(dict)
    ...     class Anyclass(MockDb):
    ...         pass
    ... except Exception, err:
    ...     pass
    ...
    >>> err
    MockException('Resources DB classes should be MockDbResourceBase based.',)
    >>>
    ... class MyMockDb(MockDb):
    ...     pass
    ...
    >>> err = ''
    >>> try:
    ...     m = MyMockDb()
    ... except Exception as err:
    ...     pass
    ...
    >>> err
    MockException('The mock DB resources must be registered.',)

    """
    def register(klass):
        if not issubclass(klass, MockDb):
            name = klass.__name__
            msg = "The class %s must be a sub class of MockDb" % name
            raise MockException(msg)
        if not all([issubclass(i, MockDbResourceBase) for i in args]):
            msg = "Resources DB classes should be MockDbResourceBase based."
            raise MockException(msg)
        setattr(klass, '_resources_db', args)
        return klass
    return register


class Resources(object):
    """ This class contains all the mock resources instances.
    """

    def __init__(self, mock_db):
        """ Dynamically sets the mock resources objects.
        """
        for ResDbClass in mock_db.get_resources_db_classes():
            setattr(self, ResDbClass.name, ResDbClass(mock_db))

    def list(self):
        """ Returns a list of all resources.
        """
        return [i for i in self.__dict__.values()
                if isinstance(i, MockDbResourceBase)]


class MockDb(object):
    """ This abstract class is the base for the NAS database that mocks the
    information of all main resources. It needs to register all DB resources
    using the @register_db_resources class decorator. Those DB resources must
    be sub-classes of the following:
     - BaseMockDbFilesystem,
     - BaseMockDbShare,
     - BaseMockDbDisk,
     - BaseMockDbPool,
     - BaseMockDbCache,
     - BaseMockDbSnapshot.
    All mocked data is stored as JSON and is loaded in memory and assigned
    to the MockDb.data attribute.
    The MockDb.data can be created/updated through the update_mock_db_data()
    method.
    """
    __metaclass__ = ABCMeta

    _resources_db_filename = 'resources.mock.json'

    data = {}  # "persistent" data in memory
    stash_backup_data = {}

    ssh_client = SSHClient

    def __init__(self, stash=False):
        """ This constructor instantiates all the db resources and also sets
        the mock database stored into mock_db_file() as a JSON format.

        >>> from mock import patch, MagicMock
        >>> from naslib.nasmock.utils import mock_open
        >>> m = mock_open(read_data='{}')
        >>> mock_isfile = lambda x : MagicMock(return_value=x)
        >>> MockDb.data = {}
        >>> @register_db_resources()
        ... class MyOtherMockDb(MockDb):
        ...     @patch('os.path.isfile', mock_isfile(False), create=True)
        ...     @patch('%s.open' % __name__, m, create=True)
        ...     def __init__(self):
        ...         super(MyOtherMockDb, self).__init__()
        ...
        >>> try:
        ...     MyOtherMockDb()
        ... except Exception, err:
        ...     pass
        ...
        >>> isinstance(err, MockException)
        True
        >>> MockDb.data = {}
        >>> m = mock_open(read_data='wrong json')
        >>> @register_db_resources()
        ... class MyOtherMockDb(MockDb):
        ...     @patch('os.path.isfile', mock_isfile(True), create=True)
        ...     @patch('%s.open' % __name__, m, create=True)
        ...     def __init__(self):
        ...         super(MyOtherMockDb, self).__init__()
        ...
        >>> try:
        ...     MyOtherMockDb()
        ... except Exception, err:
        ...     pass
        ...
        >>> isinstance(err, MockException)
        True
        >>> MockDb.data = {}
        >>> m2 = mock_open(read_data='{}')
        >>> @register_db_resources()
        ... class MyOtherMockDb(MockDb):
        ...     @patch('os.path.isfile', mock_isfile(True), create=True)
        ...     @patch('%s.open' % __name__, m2, create=True)
        ...     def __init__(self):
        ...         super(MyOtherMockDb, self).__init__()
        ...
        >>> MyOtherMockDb()
        <MyOtherMockDb>
        >>> MockDb.data = {}
        """
        if not hasattr(self, '_resources_db'):
            raise MockException('The mock DB resources must be registered.')
        self.stash = stash
        file_path = self.mock_db_file()
        if self.stash:
            MockDb.stash_backup_data = MockDb.data.copy()
        if not MockDb.data or stash:
            if not os.path.isfile(file_path):
                raise MockException("Mock DB file '%s' not found." % file_path)
            with open(file_path) as rfile:
                try:
                    self.__class__.data = simplejson.load(rfile)
                except Exception:
                    raise MockException("Unable to load mock DB file '%s'." %
                                        self.mock_db_file())
        self.resources = Resources(self)

    def __repr__(self):
        """ Representation string of this object.
        """
        return "<%s>" % self.__class__.__name__

    def prepare_command(self, cmd):
        """ This method can be overridden by the subclass to be able to do
        modifications in "cmd" argument before it is used to "execute/insert".
        """
        return cmd

    def generic_mock_output(self, cmd):  # pylint: disable=I0011,W0613
        """ This method can be overridden by the subclass to be able to
        have an alternative to force an output given a cmd. If it returns the
        tuple (None, None), the command execution "insertion" will proceed
        normally. Please refer to the "insert" method.
        """
        return None, None, None

    def error_message(self, resource, err):
        """ This method might be overridden by the sub-class to return
        the correct formatted message given a resource and the error exception
        instance.
        """
        return "%s ERROR %s" % (resource.name, str(err))

    @classmethod
    def mock_db_file(cls):
        """ Returns the "resources.mock.json" file full path location. By
        inspection, gets the path where the *subclass* implemented is located.
        """
        path = inspect.getmodule(cls).__file__  # pylint: disable=I0011,E1103
        current_dir = os.path.dirname(path)
        return os.path.join(current_dir, cls._resources_db_filename)

    @classmethod
    def pop_stash(cls):
        """ Deletes the provisory cache data and replace the database with the
        old one previously saved.
        """
        cls.data = MockDb.stash_backup_data.copy()
        cls.stash_backup_data = {}

    @classmethod
    def get_resources_db_classes(cls):
        """ Returns the resources DB classes registered.
        """
        return cls._resources_db  # pylint: disable=I0011,E1101

    @classmethod
    def get_resource_class_by_name(cls, name):
        """ Returns the resource DB class given a name.
        """
        resources = cls.get_resources_db_classes()
        return dict([(k.name, k) for k in resources])[name]

    @classmethod
    def update_mock_db_data(cls, host, username, password=None, port=22,
                            resource_name=None, mock_update=False):
        """ Logs into a NAS server and runs commands to get the output to
        construct the JSON database string and saves it into
        cls.mock_db_file() file. Each resource has the "commands_for_mock_db"
        attribute that means the command to run in the NAS server.
        Example for SFS case:
        CommandMockDb("nfs share show") -> to retrieve a list of shares.
        """
        data = {}
        ssh = cls.ssh_client(host, username, password, port, mock_db=cls()) \
             if mock_update else cls.ssh_client(host, username, password, port)

        ssh.connect()
        resources = [cls.get_resource_class_by_name(resource_name)] \
                    if resource_name else cls.get_resources_db_classes()
        for resource in resources:
            if resource.name not in data:
                data[resource.name] = dict()
            for act, cmd in resource.commands_for_mock_db.items():
                data[resource.name][act] = cmd.extract_data(ssh)
        ssh.close()

        if resource_name:
            with open(cls.mock_db_file()) as rfile:
                previous_data = simplejson.loads(rfile.read())
                previous_data.update(data)  # pylint: disable=I0011,E1103
                data = previous_data
        from .utils import mock_open
        fopen = mock_open() if mock_update else open
        with fopen(cls.mock_db_file(), 'w') as rfile:
            rfile.write(simplejson.dumps(data, indent=4 * ' '))
