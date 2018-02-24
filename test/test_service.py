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
import socket

from tempfile import mkdtemp
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse
)

from test.build_app import (force_remove_directory, setup_fake_apps)

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

from eoscompanion.main import CompanionAppService


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


def json_http_request_with_uuid(uuid, uri, query, callback):
    '''Send a new HTTP request with the UUID in the header.'''
    session = Soup.Session.new()
    query.update({
        'deviceUUID': uuid
    })

    request = session.request_http_uri('GET',
                                       soup_uri_with_query_object(uri, query))
    message = request.get_message()
    message.request_headers.append('Accept', 'application/json')
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


def local_endpoint(port, endpoint):
    '''Generate localhost endpoint from port.'''
    return 'http://localhost:{port}/{endpoint}'.format(port=port,
                                                       endpoint=endpoint)


TEST_DATA_DIRECTORY = os.path.join(TOPLEVEL_DIRECTORY, 'test_data')
FAKE_APPS = ['org.test.ContentApp', 'org.test.VideoApp']

VIDEO_APP_THUMBNAIL_EKN_ID = 'b87d21e1d15fdb26f6dcf9f33eff11fbba6f43d5'
CONTENT_APP_THUMBNAIL_EKN_ID = 'cd50d19784897085a8d0e3e413f8612b097c03f1'


def generate_flatpak_installation_directory():
    '''Generate a path for a flatpak installation directory.

    If BUILD_DIR is set, put it in there, for easy debugging. Otherwise,
    put it in a temporary directory.
    '''
    if 'BUILD_DIR' in os.environ:
        return os.path.join(os.environ['BUILD_DIR'], 'flatpak_installation')

    return mkdtemp(prefix='flatpak_installation')


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
    def test_make_connection_to_authenticate(self, quit):
        '''Ensure that we can authenticate with the serivce.'''
        def on_received_response(obj, result):
            '''Called when we receive a response from the server.'''
            stream = obj.send_finish(result)
            bytes = stream.read_bytes(8096, None)
            self.assertTrue(json.loads(bytes.get_data().decode())['status'] == 'ok')
            quit()

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('Some UUID',
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    on_received_response)

    @with_main_loop
    def test_connection_reject_if_no_uuid(self, quit):
        '''Reject connection if UUID is not provided.'''
        def on_received_response(obj, result):
            '''Called when we receive a response from the server.'''
            stream = obj.send_finish(result)
            bytes = stream.read_bytes(8096, None)
            response = json.loads(bytes.get_data().decode())
            self.assertTrue(response['status'] == 'error')
            self.assertTrue(response['error']['code'] == 'INVALID_REQUEST')
            quit()

        self.service = CompanionAppService(Holdable(), self.port)
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    on_received_response)

