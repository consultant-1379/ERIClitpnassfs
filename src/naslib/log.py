##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
""" Log class implementation based on LITP Logger.
"""

import logging


class DefaultLogger(object):
    """ Wrapper for trace logger.
    """

    def __init__(self):
        self.trace = logging.getLogger('litp.trace')


class NasLogger(object):
    """ Allows customs loggers.
    """

    logger = DefaultLogger()

    @classmethod
    def set(cls, logger):
        """ Sets the default logger class.
        >>> class MyLogger(object):
        ...     def debug(self, msg):
        ...         print msg
        ...     def info(self, msg):
        ...         print msg
        ...     def error(self, msg):
        ...         print msg
        ...     def warn(self, msg):
        ...         print msg
        ...
        >>> class TheLogger(object):
        ...     def __init__(self):
        ...         self.trace = MyLogger()
        ...
        >>> logger = TheLogger()
        >>> NasLogger.set(logger)
        >>> log = NasLogger.instance()
        >>> log.trace.debug('hello')
        hello
        >>> log.trace.info('goodbye')
        goodbye
        """
        cls.logger = logger

    @classmethod
    def instance(cls):
        return cls.logger
