##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains the base classes NAS objects representation.
It contains the following classes used to be attached in NasObjectBase
as a __metaclass__:
 - NasObjectMeta
 - NasStorageObjectMeta

Those metaclasses are implemented to attach dynamically specific exceptions to
a NASObject class.

The ExclusiveExceptions class is just to differentiate those
NasObjectBase subclasses that have exclusive exceptions attached. For
further exaplanation and examples please refer to the docstrings and doctests
in this module.
"""

from abc import ABCMeta
import inspect

from .nasexceptions import DoesNotExist, AlreadyExists, CreationException, \
                           DeletionException, SizeException, ResizeException, \
                           SameSizeException, CannotShrinkException, \
                           InsufficientSpaceException
from .resourceprops import Size


class ExclusiveExceptions(object):
    """ This class is just to differentiate those NasObjectBase
    subclasses that have exclusive exceptions attached, that's why there's no
    implementation. For further explanation and examples please refer to the
    docstrings and doctests in this module.
    """


class NasObjectMeta(ABCMeta):
    """ This metaclass is to dynamically attach specific exceptions in a
    NasObject subclass. This means that every subclass of NasObject with this
    NasObjectMeta set as __metaclass__, will have the defined exceptions
    attached to it.

    Example: if a Pool class inherits from NasObject that has the
    NasObjectMeta as __metaclass__, the Pool class will have attributes
    like:
     - Pool.DoesNotExit;
     - Pool.AlreadyExists;
     - Pool.CreationException;
     - Pool.DeletionException.
    And all of those exceptions attached are different from others with the
    same name, e.g: Pool.DoesNotExist != Share.DoesNotExist.
    """
    exceptions = [
        DoesNotExist,
        AlreadyExists,
        CreationException,
        DeletionException
    ]

    def __new__(mcs, name, bases, attr):
        """ Each exception defined in this metaclass in
        NasObjectMeta.exceptions, is dynamically attached to the target
        class as a nested exception class. Each class that wants to have an
        exclusive exception different from others, needs to have the
        ExclusiveExceptions class inherited as well.

        Example below:

        >>> class SomeBaseClass(ExclusiveExceptions):
        ...     __metaclass__ = NasObjectMeta
        ...
        >>> class Some(SomeBaseClass, ExclusiveExceptions):
        ...     pass
        ...
        >>> hasattr(Some, 'DoesNotExist')
        True
        >>> hasattr(Some, 'AlreadyExists')
        True
        >>> hasattr(Some, 'CreationException')
        True
        >>> hasattr(Some, 'DeletionException')
        True

        It is useful because the exceptions can be separately related to the
        class defined. Like the example below:

        >>> class Car(Some, ExclusiveExceptions):
        ...     pass
        ...
        >>> class Bus(Some, ExclusiveExceptions):
        ...     pass
        ...
        >>> car = Car()
        >>> bus = Bus()
        >>> car.DoesNotExist != DoesNotExist
        True
        >>> bus.DoesNotExist != DoesNotExist
        True
        >>> car.DoesNotExist != bus.DoesNotExist
        True
        >>>
        >>> # this class below is created without inherit from
        >>> # ExclusiveExceptions because should be the same as the super class
        >>> class Beetle(Car):
        ...     pass
        ...
        >>> # this example below shows that the exception of the class is the
        >>> # same as the super class.
        >>> beetle = Beetle()
        >>> car.DoesNotExist == beetle.DoesNotExist
        True
        """
        cls = super(NasObjectMeta, mcs).__new__(mcs, name, bases, attr)
        for exc in mcs.exceptions:
            exc_bases = [b for b in bases if hasattr(b, exc.__name__)]
            if exc_bases and ExclusiveExceptions not in bases:
                # attaches the exception in the class but using from the super
                # class instead of creating a new one. This means that every
                # class NOT inherited from ExclusiveExceptions but inherited
                # from classes with this NasObjectMeta set as metaclass
                # will have the same exceptions. Example below:
                # NasObject has NasObjectMeta as __metaclass__
                # Pool        inherits from NasObject,ExclusiveExceptions
                # SfsPoolItem inherits from Pool
                # So, NasObject -> Pool -> SfsPoolItem
                typ = getattr(exc_bases[0], exc.__name__)
                # Now, instead of creating a new type exception, the exceptions
                # will be the identical like:
                #      Pool.DoesNotExist == SfsPoolItem.DoesNotExist.
                # ** please refer to the example in the doctest of this method.
                #
                # It's useful for NasResourceBase classes that have the
                # resource_item_class attribute and the exceptions are being
                # used by the methods "get" and "exists".
            else:
                # attaches a new exception type, so it will be different for
                # each class that have this __metaclass__ defined.
                typ = type(exc.__name__, (exc,), {})
            setattr(cls, exc.__name__, typ)
        return cls


class Attr(object):
    """ This class is implemented just to classify/identify a NasObject
    object member from the other common attributes in a class as a particular
    attribute called Attr. Example:
     - A FileSystem concept has attributes like name, pool, size, layout.
     - A FileSystem generic class based on NasObject could also have
     several others attributes than the described above.
    """

    def __init__(self, obj):
        """ Just sets the object as an attribute of this Attr instance. The
        NasObject class overrides the __getatrribute__ method to retrieve
        the real Attr().obj instead of the instance of Attr.

        Example:

        >>> class Student(object):
        ...     def __init__(self, name, age):
        ...         self.name = Attr(name)
        ...         self.age = Attr(age)
        ...         self.score = 10
        ...         self.degree = 3
        ...
        >>> student = Student('Rogerio Hilbert', 33)
        >>> student.name
        <Attr Rogerio Hilbert>
        >>> student.age
        <Attr 33>
        >>> student.score
        10
        >>> student.degree
        3

        Those Attr attributes instances will be used by NasObject class
        when overriding the __getatrribute__ method to retrieve the real
        Attr().obj instead of the instance of Attr. For further information
        refer to the "__getattribute__" and "properties" methods of the
        NasObject class.
        """
        self.obj = obj

    def __repr__(self):
        """ Returns the representation string of this object.
        """
        return "<%s %s>" % (self.__class__.__name__, self.obj)


class LazyAttr(Attr):
    """ It represents an Attr object but for object caching purposes, giving
    a function.
    """

    def __init__(self, obj, func):
        """ As the Attr constructor, also sets function to be executed.

        Example:

        >>> class Student(NasObject):
        ...     def __init__(self, resource, name, age, score=None):
        ...         super(Student, self).__init__(resource, name)
        ...         self.age = Attr(age)
        ...         self.score = LazyAttr(score, self.get_score)
        ...     def get_score(self):
        ...         # calculates the score and returns it
        ...         calculated = self.age * 10
        ...         return calculated
        ...
        >>> student = Student(None, 'Rogerio Hilbert', 33)
        >>> student.name
        'Rogerio Hilbert'
        >>> student.age
        33
        >>> student.score
        330
        """
        super(LazyAttr, self).__init__(obj)
        self.func = func


class NasObject(ExclusiveExceptions):
    """ The base abstract class of a NAS object.
    """
    __metaclass__ = NasObjectMeta

    identifier_keys = ('name',)

    def __init__(self, resource, name):
        """ This constructor requires the resource parent as the first
        argument. The name argument is required, since we're assuming that
        every NasObject has at least a name as an identifier.
        """
        self.resource = resource
        self.name = Attr(name)

    def __str__(self):
        """ Returns this NAS object name.
        """
        return str(self.name)

    def __repr__(self):
        """ Returns the representation string of this object.
        """
        return "<%s %s>" % (self.__class__.__name__, str(self))

    def delete(self):
        """ Uses the resource parent to executes the deletion of this NasObject
        instance.
        """
        self.resource.delete(self.name)

    @property
    def attributes(self):
        """ Retrieves all attributes of this class which are instance of Attr
        or LazyAttr.
        """
        attrs = [i for i, v in self.__dict__.items()
                 if isinstance(v, Attr) or isinstance(v, LazyAttr)]
        return attrs

    @property
    def non_lazy_attributes(self):
        """ Retrieves all attributes of this class which are instance of Attr
        but not instance of LazyAttr.
        """
        attrs = [i for i, v in self.__dict__.items()
                 if isinstance(v, Attr) and not isinstance(v, LazyAttr)]
        return attrs

    def diff(self, other):
        """ Returns a dict containing the attributes names as keys and as value
        a tuple containing the different values.
        """
        if self == other:
            return {}
        attrs = self.attributes
        diff = dict([(a, (getattr(self, a), getattr(other, a))) for a in attrs
                    if getattr(self, a) != getattr(other, a)])
        return diff

    def diff_display(self, other):
        """ Retrieves the differences between two instances in terms of its
        attributes Attr as a human readable display.
        """
        diff = ["%s: %s" % (k, '"%s" != "%s"' % t) for k, t in
                self.diff(other).items()]
        return ', '.join(diff)

    def __getattribute__(self, name):
        """ Some self attributes could be an instance of Attr or LazyAttr, so
        just retrieves the real object itself, instead of Attr or LazyAttr
        instance.
        """
        value = super(NasObject, self).__getattribute__(name)
        if isinstance(value, LazyAttr):
            return value.func()
        if isinstance(value, Attr):
            return value.obj
        return value

    def __setattr__(self, name, value):
        """ Some self attributes could be an instance of Attr or LazyAttr, so
        just keep them as the same instances.
        """
        old_value = self.__dict__.get(name)
        if isinstance(old_value, Attr) and not isinstance(value, Attr):
            super(NasObject, self).__setattr__(name, Attr(value))
        elif not isinstance(old_value, LazyAttr):
            super(NasObject, self).__setattr__(name, value)

    def __eq__(self, other):
        """ Implements the equal condition operator for this NAS object.
        """
        bases = inspect.getmro(self.__class__)
        is_instance = any([isinstance(other, c) for c in bases])
        return is_instance and self.name == other.name

    def __ne__(self, other):
        """ Implements the not equal condition operator for this NAS object.
        """
        return not self.__eq__(other)


###############################################################################
# Base Nas classes for storage NAS objects like FileSystems, Disks, Caches.
# NOTE: The NasStorageObjectMeta metaclass just include more specific
# exceptions that concerns to a storage size.


class NasStorageObjectMeta(NasObjectMeta):
    """ This metaclass dynamically creates specific exceptions for each
    NASObject.

    NOTE: For further explanation of how it is implemented, refer to
    NasObjectMeta doc string above.
    """

    exceptions = NasObjectMeta.exceptions + [
        SizeException,
        ResizeException,
        SameSizeException,
        CannotShrinkException,
        InsufficientSpaceException
    ]


class NasStorageObject(NasObject, ExclusiveExceptions):
    """ Every NAS object characterized as a storage, should inherit this class,
    such as: FileSystems, Caches, etc.
    """
    __metaclass__ = NasStorageObjectMeta
    _sizeclass = Size

    def __init__(self, resource, name, size="0b"):
        """ NFS Storage resource also has a size attribute.
        """
        super(NasStorageObject, self).__init__(resource, name)
        self.size = Attr(self._sizeclass(size))

    def resize(self, size, pool=None):
        """ Uses the resource parent to execute the resize operation of this
        storage FileSystem instance.
        """
        self.resource.resize(self.name, size, pool=pool)
        self.size = Attr(self._sizeclass(size))
