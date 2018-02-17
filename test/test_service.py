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

from urllib.parse import urlencode
from unittest import TestCase
from eoscompanion.main import CompanionAppService

from gi.repository import EosCompanionAppService, GLib, Soup


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


def handle_json(handler):
    '''Handler middleware to parse bytestream for JSON response.'''
    def bytes_loaded(obj, result):
        '''Handle the loaded bytes.'''
        bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        handler(json.loads(bytes.get_data().decode()))

    def soup_bytestream_handler(obj, result):
        '''Handle the bytestream.'''
        stream = obj.send_finish(result)
        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=1024,
                                                           cancellable=None,
                                                           callback=bytes_loaded)

    return soup_bytestream_handler


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

        self.service = CompanionAppService(Holdable(), 1110)
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
            self.assertTrue(response['error']['code'] == 'INVALID_REQUEST')
            quit()

        self.service = CompanionAppService(Holdable(), 1110)
        json_http_request_with_uuid('',
                                    'http://localhost:1110/device_authenticate',
                                    {},
                                    on_received_response)

