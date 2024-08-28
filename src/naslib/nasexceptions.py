##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################


###############################################################################
# Unhandled exceptions


class NasImplementationError(Exception):
    pass


class NasDriverDoesNotExist(Exception):
    pass


###############################################################################
# Handled exceptions


class NasException(Exception):
    """ This is the base exception for all naslib.
    """
    pass


class NasIncompleteParsedInformation(NasException):
    """ In case an output is parsed with an incomplete information, this
    exception should be raised.
    """

    def __init__(self, message, parsed_data):
        super(NasIncompleteParsedInformation, self).__init__(message,
                                                             parsed_data)
        self.parsed_data = parsed_data


class NasUnexpectedOutputException(NasException):
    pass


class NasBadUserException(NasException):
    pass


class NasBadPrivilegesException(NasException):
    pass


class NasExecutionTimeoutException(NasException):
    pass


class NasExecCommandException(NasException):
    pass


class UnableToDiscoverDriver(NasException):
    pass

###############################################################################
# ResourceItem specific exceptions


class DoesNotExist(NasException):
    pass


class AlreadyExists(NasException):
    pass


class CreationException(NasException):
    pass


class DeletionException(NasException):
    pass


###############################################################################
# ResourceStorageItem specific exceptions


class SizeException(NasException):
    pass


class ResizeException(NasException):
    pass


class SameSizeException(NasException):
    pass


class CannotShrinkException(NasException):
    pass


class InsufficientSpaceException(NasException):

    def __init__(self, message, size=None):
        super(InsufficientSpaceException, self).__init__(message)
        self.size = size


###############################################################################
# NasConnection exceptions


class NasConnectionException(Exception):
    pass
