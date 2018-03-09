# /test/__init__.py
#
# Copyright (C) 2017 Endless Mobile, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# All rights reserved.
'''Package entry point for tests.'''

import errno
import json
import os
import re
import socket

from tempfile import mkdtemp
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse
)

from test.build_app import (force_remove_directory, setup_fake_apps)

import gi

gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosKnowledgeContent', '0')
gi.require_version('EosMetrics', '0')
gi.require_version('EosShard', '0')

from gi.repository import EosCompanionAppService, GLib, Soup

from testtools import (
    TestCase
)
from testtools.matchers import (
    AfterPreprocessing,
    ContainsDict,
    Equals,
    MatchesAll,
    MatchesSetwise
)

from eoscompanion.service import CompanionAppService


TOPLEVEL_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                  '..'))


def with_main_loop(testfunc):
    '''Decorator for tests to run with a main loop.

    Tests MUST call the 'quit_cb' parameter when they are finished, otherwise
    the test will never exit.
    '''
    # Need to disable docstrings here, otherwise the same docstring
    # will be printed for each test
    #
    # pylint: disable=missing-docstring
    def decorator(instance):
        caught_exception = None
        loop = GLib.MainLoop()

        def quit_handler(exception=None):
            '''Invoke loop.quit, propagating exception if required.'''
            nonlocal caught_exception

            if exception:
                caught_exception = exception

            loop.quit()

        def boot():
            '''Called after we enter the main loop.'''
            nonlocal caught_exception

            try:
                testfunc(instance, quit_handler)
            except Exception as exception:
                quit_handler(exception=exception)

        GLib.idle_add(boot)

        try:
            loop.run()
        except Exception as exception:
            caught_exception = exception

        if caught_exception:
            raise caught_exception

    return decorator


def quit_on_fail(callback, quit_func):
    '''Invoke callback, catching exceptions and propagating to quit_func.'''
    def handler(*args, **kwargs):
        '''Callback handler.'''
        try:
            callback(*args, **kwargs)
        except Exception as exception:
            quit_func(exception=exception)

    return handler


def autoquit(callback, quit_func):
    '''Invoke callback, catching exceptions and propagating to quit_func.

    Otherwise, unlike quit_on_fail, call quit_func without any arguments
    since it is assumed that this is the last callback that will
    need to be invoked before the test completes.
    '''
    def handler(*args, **kwargs):
        '''Callback handler.'''
        try:
            callback(*args, **kwargs)
            quit_func()
        except Exception as exception:
            quit_func(exception=exception)

    return handler


def soup_uri_with_query(uri, querystring):
    '''Create a new SoupURI for uri, with a querystring.'''
    soup_uri = Soup.URI.new(uri)
    soup_uri.set_query(querystring)

    return soup_uri


def soup_uri_with_query_object(uri, query_object):
    '''Create a new SoupURI for uri, with query string from query_object.'''
    return soup_uri_with_query(uri, urlencode(query_object))


def json_http_request_with_uuid(uuid, uri, query, callback, headers=None):
    '''Send a new HTTP request with the UUID in the header.'''
    session = Soup.Session.new()
    query.update({
        'deviceUUID': uuid
    })

    request = session.request_http_uri('GET',
                                       soup_uri_with_query_object(uri, query))
    message = request.get_message()
    message.request_headers.append('Accept', 'application/json')
    for header, value in (headers or {}).items():
        message.request_headers.append(header, value)

    EosCompanionAppService.set_soup_message_request(message,
                                                    'application/json',
                                                    '{}')
    request.send_async(None, callback)


class Holdable(object):
    '''A fake application placeholder that implements hold and release.'''

    def __init__(self):
        '''Initialize hold count.'''
        self.hold_count = 0

    def hold(self):
        '''Increment hold count.'''
        self.hold_count += 1

    def release(self):
        '''Decrement hold count.'''
        self.hold_count -= 1


def handle_text(handler):
    '''Handler middleware to parse bytestream for text.'''
    def bytes_loaded(_, result):
        '''Handle the loaded bytes.'''
        text_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        handler(text_bytes.get_data().decode())

    def soup_bytestream_handler(obj, result):
        '''Handle the bytestream.'''
        stream = obj.send_finish(result)
        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=1024,
                                                           cancellable=None,
                                                           callback=bytes_loaded)

    return soup_bytestream_handler


def handle_json(handler):
    '''Handler middleware to parse bytestream for JSON response.'''
    def text_loaded(text):
        '''Handle the loaded text and parse JSON.'''
        handler(json.loads(text))

    return handle_text(text_loaded)


def handle_headers_bytes(handler):
    '''Handler middleware that just returns the response headers and bytes.'''
    def soup_bytestream_handler(request_obj, result):
        '''Handle the bytestream.'''
        def bytes_loaded(_, result):
            '''Handle the loaded bytes.'''
            msg_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
            handler(msg_bytes, request_obj.get_message().response_headers)

        stream = request_obj.send_finish(result)
        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=1024,
                                                           cancellable=None,
                                                           callback=bytes_loaded)

    return soup_bytestream_handler


class GLibEnvironmentPreservationContext(object):
    '''A class to keep track of environment variables set with GLib.setenv.

    Because we interact with a code that expects environment
    variables to be set on the C side, we need to use GLib.setenv
    as opposed to just monkey-patching os.environ, which will
    not propagate changes down to environ on the stdlib.
    '''

    def __init__(self):
        '''Initialize backup dict.'''
        super().__init__()
        self._backup = {}

    def push(self, variable, value):
        '''Push a new value for this variable into the environment.

        If the variable was already backed up then the backed up value
        is not changed, it will be restored upon a call to restore().
        '''
        if variable not in self._backup:
            self._backup[variable] = GLib.getenv(variable)

        GLib.setenv(variable, value, True)

    def restore(self):
        '''Restore or unset all backed up environment variables.'''
        for variable, value in self._backup.items():
            if value is not None:
                GLib.setenv(variable, value, True)
            else:
                GLib.unsetenv(variable)


def can_listen(port):
    '''Return True if we can listen on this port.'''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((socket.gethostname(), port))
        sock.close()
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            return False
        raise error

    return True


_PORT_START = 3000
_PORT_END = 4000


def find_available_port():
    '''Scan ports to find an available one.'''
    for port in range(_PORT_START, _PORT_END):
        if can_listen(port):
            return port

    raise RuntimeError('Cannot find an available port to listen on')


def local_endpoint(port, endpoint, version='v1'):
    '''Generate localhost endpoint from port.'''
    return 'http://localhost:{port}/{version}/{endpoint}'.format(
        port=port,
        version=version,
        endpoint=endpoint
    )


TEST_DATA_DIRECTORY = os.path.join(TOPLEVEL_DIRECTORY, 'test_data')
FAKE_APPS = ['org.test.ContentApp', 'org.test.VideoApp']
FAKE_UUID = 'Some UUID'

VIDEO_APP_THUMBNAIL_EKN_ID = 'b87d21e1d15fdb26f6dcf9f33eff11fbba6f43d5'
CONTENT_APP_THUMBNAIL_EKN_ID = 'cd50d19784897085a8d0e3e413f8612b097c03f1'

VIDEO_APP_FAKE_CONTENT = (
    'Not actually an MPEG-4 file, just a placeholder for tests\n'
)


def generate_flatpak_installation_directory():
    '''Generate a path for a flatpak installation directory.

    If BUILD_DIR is set, put it in there, for easy debugging. Otherwise,
    put it in a temporary directory.
    '''
    if 'BUILD_DIR' in os.environ:
        return os.path.join(os.environ['BUILD_DIR'], 'flatpak_installation')

    return mkdtemp(prefix='flatpak_installation')


def fetch_first_content_id(app_id, tags, port, callback, quit_cb):
    '''Request a content listing and pass first content ID to callback.'''
    def on_received_response(response):
        '''Called when we receive a response from the server.'''
        callback(response['payload'][0]['id'])

    json_http_request_with_uuid(FAKE_UUID,
                                local_endpoint(port,
                                               'list_application_content_for_tags'),
                                {
                                    'applicationId': app_id,
                                    'tags': ';'.join(tags)
                                },
                                handle_json(quit_on_fail(on_received_response,
                                                         quit_cb)))


def url_matches_path(path):
    '''Check if the candidate URL matches some path.'''
    return AfterPreprocessing(lambda u: urlparse(u).path, Equals(path))


def url_matches_query(query):
    '''Check if the candidate URL matches some query structure.'''
    return AfterPreprocessing(lambda u: parse_qs(urlparse(u).query),
                              ContainsDict(query))


def matches_uri_query(path, expected_query):
    '''Check if the passed URI with a querystring matches expected_query.

    We cannot just test for string equality here - we need to parse
    the querystring and decompose its query, then match the query
    against expected_query.
    '''
    return MatchesAll(url_matches_path(path),
                      url_matches_query(expected_query))


class TestCompanionAppService(TestCase):
    '''Test suite for the CompanionAppService class.'''

    # Ensure that self.listener and self.service are set to None
    # so that the references on them are dropped
    def setUp(self):
        '''Tear down the test case.'''
        super().setUp()
        self.service = None
        self._env_context = GLibEnvironmentPreservationContext()

        self._env_context.push('EOS_COMPANION_APP_FLATPAK_SYSTEM_DIR',
                               self.__class__.flatpak_installation_dir)

        # Having to explicitly enumerate all the fake flatpaks
        # like this is not ideal, but it seems like Eknc only searches
        # the hardcoded system flatpak dirs - not sure if it should
        # also check FLATPAK_SYSTEM_DIR and FLATPAK_USER_DIR
        self._env_context.push('XDG_DATA_DIRS', os.pathsep.join([
            os.path.join(self.__class__.flatpak_installation_dir,
                         'app',
                         app_id,
                         'current',
                         'active',
                         'files',
                         'share')
            for app_id in FAKE_APPS
        ] + [
            GLib.getenv('XDG_DATA_DIRS') or '',
        ]))

        self.port = find_available_port()

    def tearDown(self):
        '''Tear down the test case.'''
        self.service.stop()
        self.service = None

        self._env_context.restore()

        super().tearDown()

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        '''Set up the entire test case class.'''
        cls.flatpak_installation_dir = generate_flatpak_installation_directory()
        setup_fake_apps(FAKE_APPS,
                        TEST_DATA_DIRECTORY,
                        cls.flatpak_installation_dir)

    @classmethod
    def tearDownClass(cls):  # pylint: disable=invalid-name
        '''Tear down the entire class by deleting build testing flatpaks.'''
        force_remove_directory(cls.flatpak_installation_dir)

    @with_main_loop
    def test_make_connection_to_authenticate(self, quit_cb):
        '''Ensure that we can authenticate with the serivce.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertTrue(response['status'] == 'ok')

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_connection_reject_if_no_uuid(self, quit_cb):
        '''Reject connection if UUID is not provided.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertTrue(response['status'] == 'error')
            self.assertTrue(response['error']['code'] == 'INVALID_REQUEST')

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_list_applications_contains_video_app(self, quit_cb):
        '''/v1/list_applications should contain video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                [a for a in response['payload'] if a['applicationId'] == 'org.test.VideoApp'][0],
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'displayName': Equals('Video App'),
                    'shortDescription': Equals('A description about a Video App'),
                    'icon': matches_uri_query('/v1/application_icon', {
                        'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    }),
                    'language': Equals('en')
                })
            )
        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_applications'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))


    @with_main_loop
    def test_list_applications_error_no_device_uuid(self, quit_cb):
        '''/v1/list_applications should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_applications'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app(self, quit_cb):
        '''/v1/application_icon should work for video app.'''
        def on_received_response(_, headers):
            '''Called when we receive a response from the server.'''
            self.assertEqual(headers.get_content_type()[0], 'image/png')

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_headers_bytes(autoquit(on_received_response,
                                                                  quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/application_icon should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_icon_name(self, quit_cb):
        '''/v1/application_icon should return an error if iconName not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_bad_icon_name(self, quit_cb):
        '''/v1/application_icon should return an error if iconName is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.this.Icon.Name.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app(self, quit_cb):
        '''/v1/application_colors should work for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['colors'],
                            MatchesSetwise(Equals('#4573d9'), Equals('#98b8ff')))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/application_colors should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_application_id(self, quit_cb):
        '''/v1/application_colors should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/application_colors should return an error if applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_colors(self, quit_cb):
        '''/v1/list_application_sets should include colors.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['colors'],
                            MatchesSetwise(Equals('#4573d9'),
                                           Equals('#98b8ff')))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_home_page_tag(self, quit_cb):
        '''/v1/list_application_sets should return EknHomePageTag for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['sets'][0], ContainsDict({
                'tags': MatchesSetwise(Equals('EknHomePageTag')),
                'title': Equals('Video App'),
                'contentType': Equals('application/x-ekncontent-set'),
                'thumbnail': matches_uri_query('/v1/application_icon', {
                    'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                }),
                'id': Equals(''),
                'global': Equals(True)
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_content_app(self, quit_cb):
        '''/v1/list_application_sets should return correct tags for content app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                sorted(response['payload']['sets'], key=lambda s: s['title'])[0],
                ContainsDict({
                    'tags': MatchesSetwise(Equals('First Tag')),
                    'title': Equals('First Tag Set'),
                    'contentType': Equals('application/x-ekncontent-set'),
                    'thumbnail': Equals(None),
                    'global': Equals(False)
                })
            )

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.ContentApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_no_device_uuid(self, quit_cb):
        '''/list_application_sets should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_no_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationID is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_home_page_tag(self, quit_cb):
        '''/v1/list_application_content_for_tags returns video content listing.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            first = response['payload'][0]
            self.assertThat(first, ContainsDict({
                'contentType': Equals('video/mp4'),
                'displayName': Equals('Sample Video'),
                'tags': MatchesSetwise(
                    Equals('EknArticleObject'),
                    Equals('EknHomePageTag'),
                    Equals('EknMediaObject')
                ),
                'thumbnail': matches_uri_query('/v1/content_data', {
                    'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_application_id(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_tags(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if tags not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationID is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.this.App.DNE',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_content_metadata_video_app(self, quit_cb):
        '''/v1/content_metadata returns some expected video content metadata.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload'], ContainsDict({
                'title': Equals('Sample Video'),
                'source': Equals('file.mp4'),
                'contentType': Equals('video/mp4'),
                'tags': MatchesSetwise(
                    Equals('EknArticleObject'),
                    Equals('EknHomePageTag'),
                    Equals('EknMediaObject')
                )
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/content_metadata returns an error if deviceUUID is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid('',
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_application_id(self, quit_cb):
        '''/v1/content_metadata returns an error if applicationId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_content_id(self, quit_cb):
        '''/v1/content_metadata returns an error if contentId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/content_metadata returns an error applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.this.App.DNE',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb),))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_bad_content_id(self, quit_cb):
        '''/v1/content_metadata returns an error contentId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_CONTENT_ID')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using a bad EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': 'nonexistent'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app(self, quit_cb):
        '''/v1/content_data returns some expected video content data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            test_string = VIDEO_APP_FAKE_CONTENT
            self.assertEqual(msg_bytes.get_data().decode('utf-8'), test_string)
            self.assertEqual(headers.get_content_length(), len(test_string))
            self.assertEqual(headers.get_content_type()[0], 'video/mp4')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_content_app(self, quit_cb):
        '''/v1/content_data returns rewritten content app data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            body = msg_bytes.get_data().decode('utf-8')

            self.assertTrue(re.match(r'^.*<img src="\/v1/content_data.*$',
                                     body,
                                     flags=re.MULTILINE | re.DOTALL) != None)

            self.assertEqual(headers.get_content_length(), len(body))
            self.assertEqual(headers.get_content_type()[0], 'text/html')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.ContentApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.ContentApp',
                               ['First Tag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_ranges(self, quit_cb):
        '''/v1/content_data returns some expected partial video content data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            # Range is inclusive, python ranges are exclusive, so add 1
            test_string = VIDEO_APP_FAKE_CONTENT
            self.assertEqual(msg_bytes.get_data().decode('utf-8'), test_string[1:11])
            self.assertEqual(headers.get_content_length(), 10)
            self.assertEqual(headers.get_content_type()[0], 'video/mp4')
            self.assertEqual(headers.get_one('Accept-Ranges'), 'bytes')
            self.assertEqual(
                headers.get_one('Content-Range'),
                'bytes 1-10/{}'.format(len(test_string))
            )

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)),
                                        headers={
                                            'Range': 'bytes=1-10'
                                        })

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/content_data returns an error if deviceUUID is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid('',
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_application_id(self, quit_cb):
        '''/v1/content_data returns an error if applicationId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_content_id(self, quit_cb):
        '''/v1/content_data returns an error if contentId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using no EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/content_data returns an error applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.this.App.DNE',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_bad_content_id(self, quit_cb):
        '''/v1/content_data returns an error contentId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_CONTENT_ID')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using bad EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': 'nonexistent'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(), self.port)
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_search_content_by_application_id(self, quit_cb):
        '''/v1/search_content is able to find content by applicationId.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications[0], ContainsDict({
                'applicationId': Equals('org.test.VideoApp')
            }))
            self.assertThat(results[0], ContainsDict({
                'displayName': Equals('Sample Video'),
                'payload': ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'contentType': Equals('video/mp4'),
                    'tags': MatchesSetwise(
                        Equals('EknArticleObject'),
                        Equals('EknHomePageTag'),
                        Equals('EknMediaObject')
                    ),
                    'thumbnail': matches_uri_query('/v1/content_data', {
                        'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                        'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    })
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_tags(self, quit_cb):
        '''/v1/search_content is able to find content by tags.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications[0], ContainsDict({
                'applicationId': Equals('org.test.VideoApp')
            }))
            self.assertThat(results[0], ContainsDict({
                'displayName': Equals('Sample Video'),
                'payload': ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'contentType': Equals('video/mp4'),
                    'tags': MatchesSetwise(
                        Equals('EknArticleObject'),
                        Equals('EknHomePageTag'),
                        Equals('EknMediaObject')
                    ),
                    'thumbnail': matches_uri_query('/v1/content_data', {
                        'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                        'contentId': MatchesSetwise(
                            Equals(VIDEO_APP_THUMBNAIL_EKN_ID)
                        ),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    })
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term(self, quit_cb):
        '''/v1/search_content is able to find content by searchTerm.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                }),
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Sample Article 1'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('First Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(Equals(CONTENT_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                }),
                ContainsDict({
                    'displayName': Equals('Sample Article 2'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('Second Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(Equals(CONTENT_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                }),
                ContainsDict({
                    'displayName': Equals('Sample Video'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.VideoApp'),
                        'contentType': Equals('video/mp4'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('EknHomePageTag'),
                            Equals('EknMediaObject')
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                            'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Sampl'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_limit_and_offset(self, quit_cb):
        '''/v1/search_content is able to apply limits and offsets.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Sample Article 2'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('Second Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(
                                Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                            ),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Sampl',
                                        'offset': 1,
                                        'limit': 1
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_applications(self, quit_cb):
        '''/v1/search_content is able to search for applications.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Content App'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp')
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Content'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_no_filters(self, quit_cb):
        '''/v1/search_content returns an error if no filters specified.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_bad_app_id(self, quit_cb):
        '''/v1/search_content returns an error if invalid applicationId is specified.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'applicationId': 'org.test.This.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))
