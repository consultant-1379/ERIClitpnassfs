##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the base classes to define the MockDb resources.
"""

from ..nasexceptions import NasExecCommandException
from .mockexceptions import MockException


class StopInsertException(Exception):
    """ This exception is used to be caught in the insert() method just to
    return instead of doing the insert action. This exception can be raised
    inside the before_insert() method.
    """


class CommandMockDb(object):
    """ This class provides a basic mechanism to extract data given a command.
    It's useful to update the DB "resources.mock.json".
    """

    def __init__(self, cmd):
        """ Requires a command.
        """
        self.cmd = cmd

    def extract_data(self, ssh):
        """ This method is just to run the provided command in self.cmd and
        returns the cleaned data.
        """
        return ssh.run(self.cmd)[1].strip()


class MockDbResourceBase(object):
    """ This is the base class for a resource database mock. It should
    be provided:
     - name: a name of the resource (example: fs, share, disk, pool). It will
             be used as the JSON key in the database.
     - nas_object_class: must provide the correspond NasObject class.
     - display_line: should be a str containing the format of a line in the
                     output of a "list" command in. Example: for shares
                     "%(name)s %(host)s (%(options)s)"
     - display_regex: it's the regular expression to catch the values from a
                      particular line in the output. See the subclasses
                      implementation below as an example.
     - regexes: must contains a dict with the following keys:
                - list: corresponds to the a list command.
                - insert: corresponds to the a create command.
                - delete: corresponds to the a delete command.
     - commands_for_mock_db: this is just for a command to list the
                             resources to gets the output for the mock
                             database purpose. Only required when needs to
                             update the JSON database file.
     - already_exists_msg: must be a string containing an error message to
                           notify duplicate creations.

    Every subclass of this class can also implements the following methods:
     - before_insert: to do some action before the data is inserted in DB.
     - after_insert: to do some action after the data is inserted in DB.
     - before_delete: to do some action before the data is removed from the DB.
     - after_delete: to do some action after the data is removed from the DB.
    """
    name = None
    nas_object_class = None
    display_line = None
    display_regex = None
    regexes = dict()
    commands_for_mock_db = None
    already_exists_msg = ""

    def __init__(self, mock_db):
        """ The first argument if an instance of MockDb.
        >>> import re
        >>> from naslib.nasmock.db import MockDb
        >>> from naslib.nasmock.basedbresource import MockDbResourceBase
        >>> class MyMockResource(MockDbResourceBase):
        ...     name = "myresource"
        ...     identifier = "name"
        ...     display_line = "%(name)s %(host)s (%(options)s)"
        ...     display_regex = re.compile(r"some regex")
        ...     regexes = dict(
        ...         list=re.compile(r"some regex"),
        ...         insert=re.compile(r"some regex"),
        ...         delete=re.compile(r"some regex")
        ...     )
        ...     commands_for_mock_db = dict(
        ...                          list=CommandMockDb("nfs something..."))
        ...     already_exists_msg = "some"
        ...
        >>> db = None
        >>> MyMockResource(db)
        <myresource>
        >>> class MyMockResource(MockDbResourceBase):
        ...     name = "myresource"
        ...     identifier = "name"
        ...     display_line = "%(name)s %(host)s (%(options)s)"
        ...     isplay_regex = re.compile(r"some regex")
        ...     commands_for_mock_db = dict(
        ...                          list=CommandMockDb("nfs something..."))
        ...     already_exists_msg = "some"
        ...
        >>> try:
        ...     MyMockResource(db)
        ... except Exception, err:
        ...     pass
        ...
        >>> err
        MockException('MyMockResource must have the following attributes \
set properly: name, identifier, regexes (as a dict with keys list, insert, \
delete containing a regular expression as value each).',)

        """
        if self.name is None or self.display_line is None or \
           self.display_regex is None:
            raise MockException("%s must have the following attributes "
                "set properly: name, identifier, regexes (as a dict with keys "
                "list, insert, delete containing a regular expression as "
                "value each)." % self.__class__.__name__)
        self._db = mock_db

    def __repr__(self):
        """ The representation string of this object
        """
        return "<%s>" % self.name

    @property
    def resources(self):
        return self._db.resources

    @classmethod
    def match_display_regex(cls, line):
        if isinstance(cls.display_regex, list):
            for r in cls.display_regex:
                match = r.match(line)
                if match:
                    return match
            return None
        return cls.display_regex.match(line)

    def _cleaned_data_list(self):
        """ Returns the data as striped lines.
        """
        db_list = self._db.data[self.name]['list']
        return [i.strip() for i in db_list.splitlines() if i.strip()]

    def _append_data(self, line):
        """ Appends a line in the mock db.
        """
        self._db.data[self.name]['list'] += "\n%s" % line

    def _remove_data(self, to_remove):
        """ Removes a line in the mock db.
        """
        lines = self._cleaned_data_list()
        lines.remove(to_remove)
        self._db.data[self.name]['list'] = '\n'.join(lines)

    def read(self, key):
        """ Reads the database entry related to this resource given a key.
        """
        return self._db.data[self.name][key]

    def write(self, key, line):
        """ Write a line string into the database of this resource given a key.
        """
        self._db.data[self.name][key] += line

    def list(self):
        """ Just retrieve the data string.
        """
        return '\n'.join(self._cleaned_data_list())

    def insert(self, **kwargs):
        """ Look the doc string of the constructor method.
        """
        kwargs = self.prepare_insert_kwargs(**kwargs)
        new_line = self.display_line % kwargs
        if self.get(**kwargs) and self.already_exists_msg:
            # if there's no already_exists_msg provided, just continue
            msg = self.already_exists_msg % kwargs if self.already_exists_msg \
                                        else "%s already exists." % str(kwargs)
            raise NasExecCommandException(msg)
        try:
            self.before_insert(**kwargs)
        except StopInsertException:
            return
        self._append_data(new_line)
        self.after_insert(**kwargs)

    def update(self, exception_if_the_same=None, **kwargs):
        """ Updates a line in database given the kwargs.
        """
        lines = []
        idk = self.nas_object_class.identifier_keys
        identifier = dict([(k, v) for k, v in kwargs.items() if k in idk])
        for line in self._cleaned_data_list():
            match = self.match_display_regex(line)
            if not match:
                lines.append(line)
                continue
            data = match.groupdict()
            line_id = dict([(k, data[k]) for k in identifier.keys()])
            if line_id == identifier:
                for key, value in data.items():
                    if key in line_id or key not in kwargs:
                        continue
                    if exception_if_the_same and value == kwargs[key]:
                        exc = exception_if_the_same
                        raise exc  # pylint:disable=I0011,E0702
                    data[key] = kwargs[key]
                line = self.display_line % data
            lines.append(line)
        self._db.data[self.name]['list'] = '\n'.join(lines)

    def exists(self, **kwargs):
        """ Tests the existence of an object given the kwargs.
        """
        return bool(self.get(**kwargs))

    def get(self, **kwargs):
        """ Gets an entry from the database given an identifier. An identifier
        actually is a dict containing kind of "primary keys" for a single
        entry in the db. Example: {'name': 'some_fs'} is an identifier for a
        file system db. {'name': 'some_share', 'host': '1.1.1.1'} is an
        identifier for a share in the db.
        """
        idk = self.nas_object_class.identifier_keys
        identifier = dict([(k, v) for k, v in kwargs.items() if k in idk])
        for line in self.list().splitlines():
            match = self.match_display_regex(line)
            if not match:
                continue
            gdict = match.groupdict()
            line_id = dict([(k, gdict[k]) for k in identifier.keys()])
            if line_id == identifier:
                return line

    def get_entry_kwargs(self, **identifier):
        """ From the get method, parses the line through the self.display_regex
        and returns the kwargs.
        """
        line = self.get(**identifier)
        match = self.match_display_regex(line or "")
        return match.groupdict() if match else {}

    def delete(self, **identifier):
        """ Uses the identifier dict to gets an entry in the db to remove it.
        """
        to_remove = self.get(**identifier)
        self.before_delete(**identifier)
        if to_remove is None:
            idt = ', '.join(["%s=%s" % (k, v) for k, v in identifier.items()])
            raise MockException("%s not found for identifier '%s'" %
                                (self.name, idt))
        self._remove_data(to_remove)
        self.after_delete(**identifier)

    def prepare_insert_kwargs(self, **kwargs):
        """ This method is called immediately before inserting data in the
        mock database, and returns the kwargs. It can be overrided by the
        sub-class and it allows to do changes in the kwargs before it is used
        to insert in the mock database.
        """
        return kwargs

    def before_insert(self, **kwargs):
        """ This method can be implemented with some checks before inserting
        and may raises a NasExecCommandException if necessary, to simulates
        for example a validation message from the server.
        """

    def after_insert(self, **kwargs):
        """ This method is called immediately after inserting. It can be used
        by the sub-class to perform necessary actions in that stage.
        """

    def before_delete(self, **kwargs):
        """ This method can be implemented with some checks before deleting
        and may raises a NasExecCommandException if necessary, to simulates
        for example a validation message from the server.
        """

    def after_delete(self, **kwargs):
        """ This method can be implemented with some checks after the deleting
        action.
        """
