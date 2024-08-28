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
for SFS resources.
"""

import re
from decimal import Decimal

from ...resourceprops import Size


class SfsSize(Size):
    """ This class is implemented to be compatible with the Symantec FileStore.
    """

    display_size_unit_regex = re.compile(r"[\.\d]+(\w)")
    block_size = 512

    def __new__(cls, size, display_size, fs_resource_item, *args, **kwargs):
        """ The size argument of this constructor is an int that correspond the
        length in blocks of 512. The display_size argument is especially used
        in __str__ method, that reflects the SFS console display size human
        readable.
        """
        bsize = "%sb" % (size * cls.block_size)
        self = super(SfsSize, cls).__new__(cls, bsize, *args, **kwargs)
        self.display_size = display_size
        self.fs_resource_item = fs_resource_item
        return self

    def __repr__(self):
        """ Returns the representation string of this object
        >>> SfsSize(22016, "10.75M", "<SfsFileSystemItem Instance>")
        <SfsSize 10.75M>
        >>> SfsSize(22016, "11008k", "<SfsFileSystemItem Instance>")
        <SfsSize 11008.00K>
        >>> SfsSize(22010, "11008k", "<SfsFileSystemItem Instance>")
        <SfsSize 11008k ~ 11269120=22010 (blocks of 512 bytes)>
        """
        return "<SfsSize %s>" % str(self)

    def __str__(self, *args, **kwargs):
        """ Returns the size and unit as a str.
        """
        match = self.display_size_unit_regex.match(self.display_size)
        unit = match.groups()[0]
        bsize_str = "%sb" % self.num_bytes
        s = Size(bsize_str).number_in_unit(unit).quantize(Decimal("0.01"))
        size = Size(Size._display(s, unit))
        if Size(self.display_size) == size:
            return str(size)
        blocks = self.num_bytes / self.block_size
        display = "%s ~ %s=%s (blocks of 512 bytes)" % (self.display_size,
                                                        self.num_bytes, blocks)
        return display

    def _cmp(self, other):
        """ Overrides the Decimal _cmp method. In case of difference between
        two sizes, we need to check whether exist a small difference between
        then in terms of bytes. So we need to get the real number of bytes in
        the file system instead of the rounded one displayed in the SFS
         console.
        We also need to get the alignment size in bytes of the disk group to
        make the proper calculations.

        SFS file systems always have its sizes rounded by the next lowest, not
        the nearest, multiple of the sector size. (https://sort.symantec.com
        /public/documents/sfha/5.1sp1/aix/manualpages/html/manpages/
        volume_manager/html/man1m/vxintro.1m.html).

        Knowing that, the "other" file system size should be aligned properly
        to perform a fair comparison, in which SFS will expect. Small example
        of this situation:
         - Imagine a file system called "fs" with size displayed in SFS console
           by the command "storage fs list" as 10.75M. To know the exactly size
           in bytes for comparison reasons we use the "vxprint" command to get
           it.
         - Assuming that the disk alignment size is 8K.
         - The size 10.75M = 11008K.
         - According to the "vxintro" documentation SFS rounds the size to the
           next multiple, so if we create a file system through the SFS console
           like:
                $ "storage fs create simple fs2 11005k pool"
           actually SFS will create a file system with 11008K, but not 11005K,
           because it's rounded by the multiple of 8k, as we assumed as the
           alignment size.
         - 10.75M == 11008k != 11005k, but SfsSize("10.75M",) == Size("11005k")
         - Some examples:
           - Size("10.75M") != Size("11005k")
           - SfsSize("10.75M", fs_res) == Size("11005k") # from SFS perspective
           - Size("11005k") != SfsSize("10.75M", fs_res) # Size perspective
        """
        _cmp = super(SfsSize, self)._cmp(other)
        if _cmp != 0:
            alignment = self.fs_resource_item.disk_alignment
            other_num_bytes = other.num_bytes
            rest = other_num_bytes % alignment
            if rest != 0:
                other_num_bytes += alignment - rest
            if self.num_bytes == other_num_bytes:
                return 0
            else:
                return _cmp
        return _cmp
