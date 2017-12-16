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

import json
import os
import sys

os.environ['GI_TYPELIB_PATH'] = os.pathsep.join([
    os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            os.pardir
        )
    ),
    os.environ.get('GI_TYPELIB_PATH', '')
])

from unittest import TestCase
from eoscompanion.main import CompanionAppService

from gi.repository import EosCompanionAppService, GLib, Soup


def with_main_loop(testfunc):
    '''Decorator for tests to run with a main loop.
    
    Tests MUST call the 'quit' parameter when they are finished, otherwise
    the test will never exit.
    '''
    def decorator(instance):
        caught_exception = None
        loop = GLib.MainLoop()

        def boot():
            nonlocal caught_exception

            try:
                testfunc(instance, lambda: loop.quit())
            except Exception as e:
                caught_exception = e
                loop.quit()

        GLib.idle_add(boot)

        try:
            loop.run()
        except Exception as e:
            caught_exception = e

        if caught_exception:
           print('Caught a {}'.format(caught_exception), file=sys.stderr)
           raise caught_exception

    return decorator


def json_http_request_with_uuid(uuid, uri, body, callback):
    '''Send a new HTTP request with the UUID in the header.'''
    session = Soup.Session.new()
    request = session.request_http_uri('POST', Soup.URI.new(uri))
    message = request.get_message()
    message.request_headers.append('X-Endless-CompanionApp-UUID', uuid)
    message.request_headers.append('Accept', 'application/json')
    EosCompanionAppService.set_soup_message_request(message,
                                                    'application/json',
                                                    json.dumps(body))
    request.send_async(None, callback)


class TestCompanionAppService(TestCase):
    '''Test suite for the CompanionAppService class.'''

    # Ensure that self.listener and self.service are set to None
    # so that the references on them are dropped
    def setUp(self):
        '''Tear down the test case.'''
        self.service = None

    def tearDown(self):
        '''Tear down the test case.'''
        self.service.stop()
        self.service = None

    @with_main_loop
    def test_make_connection_to_authenticate(self, quit):
        '''Ensure that we can authenticate with the serivce.'''
        def on_received_response(obj, result):
            '''Called when we receive a response from the server.'''
            stream = obj.send_finish(result)
            bytes = stream.read_bytes(8096, None)
            self.assertTrue(json.loads(bytes.get_data().decode())['status'] == 'ok')
            quit()

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1110)
        json_http_request_with_uuid('Some UUID',
                                    'http://localhost:1110/device_authenticate',
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
            self.assertTrue(response['error']['code'] == EosCompanionAppService.Error.ERROR_INVALID_REQUEST)
            quit()

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1110)
        json_http_request_with_uuid('',
                                   'http://localhost:1110/device_authenticate',
                                   {},
                                   on_received_response)

