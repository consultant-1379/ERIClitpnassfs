##############################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
import json
import mock

from .unityrest import UnityREST


class MockedRequestsResponse(object):
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.content = None
        self.headers = {
            'EMC-CSRF-TOKEN': 'xxxx'
        }
        if self.json_data is not None:
            self.content = json.dumps(json_data)
            self.headers['Content-type'] = 'application/json'

    def json(self):
        return self.json_data


class UnityRESTMocker(object):
    requests_expected = []
    mocked_responses = []
    hostname = None

    @classmethod
    def setup(cls, hostname):
        cls.hostname = hostname
        UnityREST.set_mock(
            mock.MagicMock(
                name="request",
                side_effect=UnityRESTMocker.mocked_requests_request
            )
        )
        cls.logout_url = \
            "https://%s/api/types/loginSessionInfo/action/logout" % hostname

    @classmethod
    def load(cls, file_name):
        with open(file_name) as json_file:
            data = json.load(json_file)
            for entry in data:
                cls.add_request(
                    entry['method'],
                    entry['endpoint'],
                    entry['json_in'],
                    entry['status_code'],
                    entry['json_out']
                )

    @classmethod
    def reset(cls):
        cls.requests_expected = []
        cls.mocked_responses = []

    @classmethod
    def add_request(cls, method, endpoint, json_in, status_code, json_out):

        cls.requests_expected.append(
            {
                'method': method,
                'url': "https://%s%s" % (cls.hostname, endpoint),
                'json': json_in
            }
        )

        cls.mocked_responses.append(
            {
                'status_code': status_code,
                'json_data': json_out
            }
        )

    @staticmethod
    def mocked_requests_request(method, url, **kwargs):
        if 'json' in kwargs:
            json_data = kwargs['json']
        else:
            json_data = None

        # Handling for logout
        if method == 'POST' and url == UnityRESTMocker.logout_url:
            return MockedRequestsResponse(None, 200)

        if len(UnityRESTMocker.requests_expected) == 0:
            raise Exception(
                "No more request excepted, got %s %s %s" % (
                    method,
                    url,
                    str(json_data)
                )
            )

        request_expected = UnityRESTMocker.requests_expected.pop(0)

        if url != request_expected['url'] or \
            method != request_expected['method'] or \
            cmp(json_data, request_expected['json']) != 0:
            url_same = url == request_expected['url']
            url_msg = "url_same=%s" % url_same
            if not url_same:
                url_msg = UnityRESTMocker._check_url(
                    url,
                    request_expected['url'],
                    url_msg
                )
            method_same = method == request_expected['method']
            json_same = cmp(json_data, request_expected['json']) == 0

            msg_pt1 = "Unexpected request url compare=[%s] method_same=%s " % (
                url_msg,
                method_same
            )
            msg_pt2 = "json_same=%s Got %s %s %s, expected %s %s %s" % (
                json_same,
                method,
                url,
                str(json_data),
                request_expected['method'],
                request_expected['url'],
                str(request_expected['json'])
            )
            raise Exception("%s %s" % (msg_pt1, msg_pt2))

        mocked_response_data = UnityRESTMocker.mocked_responses.pop(0)
        return MockedRequestsResponse(
            mocked_response_data['json_data'],
            mocked_response_data['status_code']
        )

    @staticmethod
    def _check_url(url, expected_url, url_msg):
        expected_path = expected_url.split('?')[0]
        actual_path = url.split('?')[0]
        path_same = expected_path == actual_path
        url_msg = url_msg + ", path_same=%s" % path_same
        if not path_same:
            url_msg = url_msg + ",expected_path=%s,actual_path=%s" % (
                expected_path,
                actual_path
            )
        else:
            expected_args = \
                expected_url.split('?')[1].split('&')
            actual_args = url.split('?')[1].split('&')
            if len(expected_args) != len(actual_args):
                url_msg = url_msg + ", %s != %s" % (
                    actual_args,
                    expected_args
                )
            else:
                for index, expected_arg in enumerate(expected_args, 0):
                    actual_arg = actual_args[index]
                    if expected_arg != actual_arg:
                        url_msg = url_msg + ", %s != %s" % (
                            expected_arg,
                            actual_arg
                        )
        return url_msg
