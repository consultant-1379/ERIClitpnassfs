##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains basically unit tests.
"""

import unittest

from decimal import Decimal
from random import shuffle

from naslib.resourceprops import StringOptions, Size, SizeDoesNotMatch, \
                                 ResourcePropertyException, UnitsSize


class TestResourceProperties(unittest.TestCase):

    def test_size(self):
        self._test_size(Size)

    def _test_size(self, sc):
        for num in xrange(10, 210, 30):
            for dec in xrange(1, 100, 15):
                kilos = "%s.%sk" % (num, dec)
                self.assertEquals(sc(kilos), sc(kilos))
                megas = "%s.%sm" % (num, dec)
                self.assertEquals(sc(megas), sc(megas))
                gigas = "%s.%sg" % (num, dec)
                self.assertEquals(sc(gigas), sc(gigas))
                teras = "%s.%st" % (num, dec)
                self.assertEquals(sc(teras), sc(teras))
        units = ['k', 'm', 'g', 't']
        size = "10%s"
        for u1 in units:
            for u2 in units:
                if u1 == u2:
                    self.assertEquals(sc(size % u1), sc(size % u2))
                else:
                    self.assertNotEquals(sc(size % u1), sc(size % u2))
        for num in xrange(10, 20):
            self.assertEquals(sc("%sk" % (num * 1024)), sc("%sm" % num))
            self.assertEquals(sc("%sm" % (num * 1024)), sc("%sg" % num))
            self.assertEquals(sc("%sg" % (num * 1024)), sc("%st" % num))

        self.assertEquals(sc("2m"), sc("2048k"))
        self.assertEquals(sc("1.5m"), sc("1536k"))

        kilo = Decimal("1")
        mega = kilo * Decimal("1024")
        giga = mega * Decimal("1024")
        tera = giga * Decimal("1024")

        for num in xrange(10, 210, 30):
            for dec in xrange(1, 100, 5):
                dec = "%s.%s" % (num, dec)
                megas = "%sm" % dec
                kilos = "%sk" % (Decimal(dec) * mega)
                self.assertEquals(sc(kilos), sc(megas))
                gigas = "%sg" % dec
                kilos = "%sk" % (Decimal(dec) * giga)
                self.assertEquals(sc(kilos), sc(gigas))
                teras = "%st" % dec
                kilos = "%sk" % (Decimal(dec) * tera)
                self.assertEquals(sc(kilos), sc(teras))
                gigas = "%sg" % dec
                megas = "%sm" % (Decimal(dec) * mega)
                self.assertEquals(sc(megas), sc(gigas))
                teras = "%st" % dec
                megas = "%sm" % (Decimal(dec) * giga)
                self.assertEquals(sc(megas), sc(teras))
                teras = "%st" % dec
                gigas = "%sg" % (Decimal(dec) * mega)
                self.assertEquals(sc(gigas), sc(teras))

        self.assertEquals(sc("1m") - sc("512k"), sc("0.5m"))
        self.assertEquals(sc("20g") + sc("1t"), sc("1044g"))

        self.assertTrue(sc("20g") == sc("20g"))
        self.assertFalse(sc("20g") != sc("20g"))
        self.assertTrue(sc("1m") == sc("1024k"))
        self.assertFalse(sc("1m") != sc("1024k"))
        self.assertTrue(sc("1g") != sc("2g"))
        self.assertFalse(sc("1g") == sc("2g"))

        self.assertRaises(SizeDoesNotMatch, Size, "10.5o")
        self.assertRaises(SizeDoesNotMatch, Size, "aaaa")
        self.assertRaises(SizeDoesNotMatch, Size, "10")

        self.assertTrue(sc("1m").kilos == sc("1024k"))
        self.assertTrue(sc("1g").megas == sc("1024m"))
        self.assertTrue(sc("1t").gigas == sc("1024g"))
        self.assertTrue(sc("1024g").teras == sc("1t"))

        self.assertEqual(sc('10M') + sc('10M'), sc('20M'))
        self.assertEqual(sc('10M') + sc('5M'), sc('15M'))
        self.assertEqual(sc('10M') + sc('1024K'), sc('11M'))

        self.assertEqual(sc('10M') - sc('10M'), sc('0M'))
        self.assertEqual(sc('10M') - sc('5M'), sc('5M'))
        self.assertEqual(sc('10M') - sc('1024K'), sc('9M'))

        self.assertEqual(sc('10G') * 10, sc('100G'))
        self.assertEqual(sc('10G') * 5, sc('50G'))
        self.assertEqual(sc('10G') * Decimal('0.5'), sc('5G'))
        self.assertEqual(sc('10M') * 10, sc('100M'))
        self.assertEqual(sc('10M') * 5, sc('50M'))
        self.assertEqual(sc('10M') * Decimal('0.5'), sc('5M'))

        self.assertEqual(sc('10G') / 10, sc('1G'))
        self.assertEqual(sc('10G') / 5, sc('2G'))
        self.assertEqual(sc('10G') / sc('10G'), sc('1B'))

        self.assertEqual(Size('-10M') + Size('1M') + Size('11M') - Size('5M')
                         - Size('256K') + Size('3.25M'), Size('0B'))

    def test_string_options(self):
        options = 'rw,ro,soft,foo,bar'

        for i in xrange(10):
            shuffled = options.split(',')[:]
            shuffle(shuffled)
            shops = ','.join(shuffled)
            self.assertEquals(StringOptions(options), StringOptions(shops))
            self.assertNotEquals(StringOptions(options),
                                 StringOptions(shops + ',some'))

        self.assertEquals(StringOptions("rw,soft"), StringOptions("soft,rw"))
        self.assertNotEquals(StringOptions("rw"), StringOptions("soft,rw"))
        self.assertNotEquals(StringOptions("rw,soft"), "rw,soft")
        self.assertEquals(StringOptions("rw,soft"), StringOptions(u"soft,rw"))
        self.assertRaises(ResourcePropertyException, StringOptions, 10)
        self.assertRaises(ResourcePropertyException, StringOptions, (10, 9))
        self.assertRaises(ResourcePropertyException, StringOptions, ("r", "a"))

        self.assertTrue(StringOptions("rw,soft") == StringOptions("soft,rw"))
        self.assertFalse(StringOptions("rw,soft") != StringOptions("soft,rw"))
        self.assertFalse(StringOptions("rw,soft") == StringOptions("soft"))
        self.assertTrue(StringOptions("rw,soft") != StringOptions("soft"))
        self.assertTrue(StringOptions("rw,soft") != "rw,soft")
        self.assertFalse(StringOptions("rw,soft") == "rw,soft")
        self.assertTrue(StringOptions("rw,soft") != True)
        self.assertTrue(StringOptions("rw,soft") != False)
        self.assertFalse(StringOptions("rw,soft") == True)
        self.assertFalse(StringOptions("rw,soft") == False)
