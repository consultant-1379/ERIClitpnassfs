##############################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
import logging
import json
import requests
import urllib3
from time import sleep

from ..nasexceptions import NasConnectionException, \
    NasExecCommandException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UnityREST(object):
    mock = None

    @classmethod
    def set_mock(cls, mock):
        cls.mock = mock

    def __init__(self, logger):
        """
        Set up logging and session.
        """
        self.__ip_address = None

        parent_logger = logger
        self.logger = logging.getLogger("%s.rest" % parent_logger.name)

        self.unity = requests.Session()
        self.unity.headers.update(
            {
                'X-EMC-REST-CLIENT': 'true',
                "Content-type": "application/json",
                "Accept": "application/json"
            }
        )

        if self.mock is not None:
            self.unity.request = self.mock

    def login(self, ip_address, username, password):
        self.__ip_address = ip_address
        self.unity.auth = (username, password)

        response = self.get_type_instances("loginSessionInfo")
        if response.status_code == 401:
            raise NasConnectionException("Login failed", 1)

        self.unity.headers.update(
            {
                'EMC-CSRF-TOKEN': response.headers['EMC-CSRF-TOKEN']
            }
        )

    def request(self, endpoint, method='GET', data=None):
        url = "https://" + self.__ip_address + endpoint

        # We want any changes made to the Unity to always be logged
        if method == 'POST' or method == 'DELETE':
            level = logging.INFO
        else:
            level = logging.DEBUG

        log_data = str(data)
        if data and 'password' in data:
            data_nopw = data.copy()
            data_nopw.pop("password")
            log_data = str(data_nopw)

        self.logger.log(
            level,
            "request: endpoint=%s method=%s data=%s" % (
                endpoint,
                method,
                log_data
            )
        )

        tries = 3
        delay = 3
        while tries >= 0:
            self.logger.log(
                    logging.INFO,
                    "request: attempts remaining=%s" %
                        tries
                )
            if tries == 0:
                raise NasConnectionException(
                        "request: request attempts exceeded"
                    )
            try:
                response = self.unity.request(method, url, json=data,
                                              verify=False)
            except (requests.exceptions.ConnectionError) as exception:
                self.logger.log(
                        logging.INFO,
                        "request: exception=%s endpoint=%s" %
                            (exception, endpoint)
                    )
                tries -= 1
                self.logger.log(
                        logging.INFO,
                        "request: delay for %s seconds" % delay
                    )
                sleep(delay)
            else:
                break

        self.logger.log(
            level,
            "request: response status_code %s" % response.status_code
        )
        self.logger.log(level, "request: content %s" % str(response.content))
        if response.content is not None and len(response.content) > 0 \
            and 'content-type' in response.headers \
            and response.headers['content-type'] == 'application/json':
            self.logger.level(
                level,
                "request: json=%s" % (
                    json.dumps(response.json(), indent=4, sort_keys=True)
                )
            )

        return response

    def get_type_instances(self, typename, fields=None, filter_arg=None):
        query_args = []
        if filter_arg is not None and len(filter_arg) > 0:
            query_args.append('filter=%s' % " and ".join(filter_arg))
        if fields is not None and len(fields) > 0:
            query_args.append('fields=%s' % ','.join(fields))
        url = '/api/types/%s/instances' % typename
        if len(query_args) > 0:
            url = "%s?%s" % (url, '&'.join(query_args))
        response = self.request(url)
        return response

    def get_type_instance_for_id(self, typename, id_arg, fields):
        response = self.request(
            '/api/instances/%s/%s?fields=%s' % (
                typename,
                id_arg,
                ",".join(fields)
            )
        )
        if response.status_code == 200:
            return response.json()['content']
        elif response.status_code == 404:
            return None
        else:
            raise NasExecCommandException(
                "Search for %s/%s failed with http_error=%s" %
                    (typename, id_arg, response.status_code),
                1
            )

    def get_type_instance_for_name(self, typename, instname, fields):
        response = self.request(
            '/api/instances/%s/name:%s?fields=%s' % (
                typename,
                instname,
                ",".join(fields)
            )
        )
        if response.status_code == 200:
            return response.json()['content']
        elif response.status_code == 404:
            return None
        else:
            raise NasExecCommandException(
                "Search for %s/%s failed with http_error=%s" %
                    (typename, instname, response.status_code),
                1
            )

    def get_id_for_name(self, typename, instname):
        content = self.get_type_instance_for_name(typename, instname, ["id"])
        if content is not None:
            return content['id']
        else:
            return None

    @staticmethod
    def get_response_error(response):
        response_json = response.json()
        if 'error' in response_json and 'messages' in response_json['error']:
            messages = response_json['error']['messages']
            if len(messages) > 0:
                return messages[0].values()[0]
        return "Unknown error"

    def delete_instance(self, typename, id_arg):
        endpoint = '/api/instances/%s/%s' % (typename, id_arg)
        response = self.request(endpoint, 'DELETE')
        if response.status_code != 204:
            raise NasExecCommandException(
                "Delete of %s/%s failed: %s" %
                    (typename, id_arg, self.get_response_error(response)),
                1
            )

    def create_post(self, endpoint, request_data):
        response = self.request(endpoint, 'POST', request_data)
        good_responses = [200, 201, 204]
        if response.status_code not in good_responses:
            raise NasExecCommandException(
                "Create using %s failed: %s" %
                    (endpoint, self.get_response_error(response)),
                1
            )
        return response

    def create_instance(self, typename, request_data):
        endpoint = '/api/types/%s/instances' % typename
        return self.create_post(endpoint, request_data)

    def action(self, instance_type, instance, action, request_data):
        endpoint = '/api/instances/%s/%s/action/%s' % (
            instance_type,
            instance,
            action
        )
        response = self.request(endpoint, 'POST', request_data)
        if response.status_code != 204 and response.status_code != 200:
            raise NasExecCommandException(
                "action %s failed for %s/%s: %s" % (
                    action,
                    instance_type,
                    instance,
                    self.get_response_error(response)
                ),
                1
            )
        return response
