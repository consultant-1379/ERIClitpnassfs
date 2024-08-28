##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" This module contains some util functions.
"""


def mock_open(read_data=''):
    """ Idea from original mock.py 1.0.1. Jenkins now uses version 0.8.0.
    `read_data` is a string for the `read` method of the file handle to return.
    This is an empty string by default.
    """
    # litp product doesn't support mock, use this just for test cases
    from mock import MagicMock
    mock = MagicMock(name='open', spec=open)
    handle = MagicMock(spec=file)
    handle.write.return_value = None
    handle.__enter__.return_value = handle
    handle.read.return_value = read_data
    mock.return_value = handle
    return mock
