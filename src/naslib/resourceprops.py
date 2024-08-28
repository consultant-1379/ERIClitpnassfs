##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains implementation of util classes for some properties
for nas resources.
"""

import re
from decimal import Decimal


class ResourcePropertyException(Exception):
    pass


class StringOptions(object):
    """ This class implements string options as a list of string separated by
    comma.
    """

    def __init__(self, options_str):
        """ The options_str should be an instance of str, separated by comma.
        """
        if not isinstance(options_str, basestring):
            raise ResourcePropertyException("options_str '%s' should be a "
                                            "basestring")
        self._options_str = options_str

    def __repr__(self):
        """ Returns the representation string of this object
        >>> StringOptions('rw,soft,foo,bar')
        <StringOptions rw,soft,foo,bar>
        """
        return "<StringOptions %s>" % self._cleaned()

    def __str__(self):
        """ Returns the string options cleaned
        >>> str(StringOptions('rw,soft,foo,bar'))
        'rw,soft,foo,bar'
        """
        return self._cleaned()

    @property
    def list(self):
        """ It's the string options in a list.
        >>> options = StringOptions('rw,soft,foo,bar')
        >>> options.list
        ['rw', 'soft', 'foo', 'bar']
        """
        return [i.strip() for i in self._options_str.split(',')]

    def _cleaned(self):
        """ Returns the string options cleaned
        """
        return ','.join(self.list)

    def __eq__(self, other):
        """ Compares the two sets of options whether matches or not.
        >>> StringOptions('rw,soft,foo') == StringOptions('soft,foo,rw')
        True
        >>> StringOptions('rw,soft') == StringOptions('soft,foo,rw')
        False
        >>> StringOptions('rw,soft') == 'rw,soft'
        False
        """
        if not isinstance(other, StringOptions):
            return False
        return set(self.list) == set(other.list)

    def __ne__(self, other):
        """ Compares the two sets of options whether matches or not.
        >>> StringOptions('rw,soft,foo') != StringOptions('soft,foo,rw')
        False
        >>> StringOptions('rw,soft') != StringOptions('soft,foo,rw')
        True
        >>> StringOptions('rw,soft') != 'rw,soft'
        True
        """
        return not self.__eq__(other)


class SizeDoesNotMatch(Exception):
    pass


class UnitSizeNotAllowed(Exception):
    pass


class UnitSize(int):
    pass


class UnitsSize(object):
    b = UnitSize(1)
    k = UnitSize(1024 * b)
    m = UnitSize(1024 * k)
    g = UnitSize(1024 * m)
    t = UnitSize(1024 * g)

    @classmethod
    def allowed_units(cls):
        units = [(getattr(cls, a), (str(a).lower(), getattr(cls, a))) for a
                 in dir(cls) if isinstance(getattr(cls, a), UnitSize)]
        units.sort()
        return [i[1] for i in units]

    @classmethod
    def allowed_units_str(cls):
        allowed = [i[0] for i in cls.allowed_units()]
        return ''.join(allowed) + ''.join([a.upper() for a in allowed])


class SizeMeta(type):
    """ This metaclass dynamically overrides the math operation methods.
    """

    operations = ['add', 'sub', 'mul', 'div', 'truediv', 'divmod', 'mod',
        'floordiv', 'pow']
    operations = ['__%s__' % o for o in operations]

    def __new__(mcs, name, bases, attrs):

        def new_func(member):
            def func(self, other, context=None):
                result = member(self, other, context)
                if isinstance(result, Size):
                    return result
                size = Size('%sb' % result)
                if abs(result) <= Decimal(1024 - 1):
                    return size
                elif abs(result) <= Decimal(1024 ** 2 - (1 * 1024)):
                    return size.kilos
                elif abs(result) <= Decimal(1024 ** 3 - (1 * (1024 ** 2))):
                    return size.megas
                elif abs(result) <= Decimal(1024 ** 4 - (1 * (1024 ** 3))):
                    return size.gigas
                else:
                    return size.teras
            return func

        for op in mcs.operations:
            attrs[op] = new_func(getattr(bases[0], op))

        return type.__new__(mcs, name, bases, attrs)


class Size(Decimal):
    """ It wraps the size of file systems for comparison and math operations
    purposes.
    """

    __metaclass__ = SizeMeta

    size_regex = re.compile(r"^\s*([\-]{0,1})([\d\.]+)\s*([%s]{1})\s*$" %
                            UnitsSize.allowed_units_str())

    def __new__(cls, value, *args, **kwargs):
        """ The size must match the size_regex.
        >>> Size("1024m") == Size("1g")
        True
        >>> Size("1t") / Decimal("2") == Size("0.5t")
        True
        >>> Size("1.5m") + Size("512k") == Size("2m")
        True
        """
        value = str(value)
        match = cls.size_regex.match(value)
        if match is None:
            raise SizeDoesNotMatch("The size %s doesn't match format" % value)
        _sign, digit, unit = match.groups()
        sign = -1 if _sign else 1
        unit = unit.lower()
        num_bytes = Size._convert_to_bytes(digit, unit) * sign
        self = super(Size, cls).__new__(cls, num_bytes, *args, **kwargs)
        self.__unit = unit
        self.__bytes = num_bytes
        return self

    def __repr__(self):
        """ Returns the representation string of this object
        >>> Size("2.5t")
        <Size 2.5T>
        """
        return "<Size %s>" % str(self)

    def __str__(self, *args, **kwargs):
        """ Returns the size and unit as a str.
        >>> str(Size("1k"))
        '1K'
        >>> str(Size("2k"))
        '2K'
        """
        unit_num_bytes = Size._unit_num_bytes(self.unit)
        return Size._display((self.__bytes / unit_num_bytes), self.unit)

    @staticmethod
    def _clean_unit(unit):
        """ Validates the size unit whether is allowed or not and returns it as
        a lower case.
        >>> Size._clean_unit('K')
        'k'
        >>> Size._clean_unit('G')
        'g'
        >>> Size._clean_unit('m')
        'm'
        >>> try:
        ...    Size._clean_unit('X')
        ... except Exception, err:
        ...    pass
        ...
        >>> err
        UnitSizeNotAllowed('The unit size x must be one of the: b, k, m, g, \
t',)
        """
        unit = unit.lower()
        allowed = [i[0] for i in UnitsSize.allowed_units()]
        if unit.lower() not in allowed:
            raise UnitSizeNotAllowed("The unit size %s must be one of the: %s"
                                % (unit, ', '.join(allowed)))
        return unit

    @classmethod
    def _display(cls, digit, unit):
        """ Return a string as the default format of a storage Size:
        >>> Size._display(10, 'k')
        '10K'
        >>> Size._display(2.5, 'g')
        '2.5G'
        """
        unit = cls._clean_unit(unit)
        return "%s%s" % (digit, unit.upper())

    @classmethod
    def _unit_num_bytes(cls, unit):
        """ Return the number of bytes given a unit in: K, M, G, T.
        """
        unit = cls._clean_unit(unit)
        return Decimal(str(getattr(UnitsSize, unit)))

    @classmethod
    def _convert_to_bytes(cls, digit, unit):
        """ Return the number of bytes given a digit and a unit in: K, M, G, T.
        """
        unit = cls._clean_unit(unit)
        return Decimal(digit) * Size._unit_num_bytes(unit)

    @classmethod
    def convert_bytes_to_unit(cls, num_bytes, convert_unit):
        """ Coverts num_bytes to a given unit in: K, M, G, T.
        """
        convert_unit = Size._clean_unit(convert_unit)
        return num_bytes / Size._unit_num_bytes(convert_unit)

    def number_in_unit(self, convert_unit):
        """ Return the number of bytes given a digit and a unit in: K, M, G, T.
        """
        return Size.convert_bytes_to_unit(self.num_bytes, convert_unit)

    def convert_to_unit(self, convert_unit):
        """ Returns the size converted to the given unit.
        """
        digit = Size.convert_bytes_to_unit(self.num_bytes, convert_unit)
        return Size("%s%s" % (digit, convert_unit))

    @property
    def num_bytes(self):
        """ Return the number of bytes of this size object.
        """
        return self.__bytes

    @property
    def half_k_blocks(self):
        """ Return the number of blocks in (512 bytes) of this size object.
        """
        return self.num_bytes / 512

    @property
    def digit(self):
        """ Return the digit size in the current default unit.
        """
        return self.number_in_unit(self.__unit)

    @property
    def unit(self):
        """ Return the unit of this size object.
        """
        return self.__unit

    @property
    def kilos(self):
        """ Returns this object size as kilos Size.
        """
        return self.convert_to_unit('k')

    @property
    def megas(self):
        """ Returns this object size as megas Size.
        """
        return self.convert_to_unit('m')

    @property
    def gigas(self):
        """ Returns this object size as gigas Size.
        """
        return self.convert_to_unit('g')

    @property
    def teras(self):
        """ Returns this object size as teras Size.
        """
        return self.convert_to_unit('t')
