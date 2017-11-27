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

from gi.repository import Avahi, EosCompanionAppService, GLib, Soup


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


AVAHI_IF_UNSPEC = -1
AVAHI_PROTO_UNSPEC = -1


class AvahiServiceListener(object):

    def __init__(self,
                 service_found_callback=None,
                 failure_callback=None,
                 *args,
                 **kwargs):
        '''Start up the listener'''
        super().__init__(*args, **kwargs)
        self.service_found_callback = service_found_callback
        self.failure_callback = failure_callback

        # We have to be a bit careful here and assign to self so as
        # to keep references alive. Not ideal.
        self.browser = Avahi.ServiceBrowser.new('_eoscompanion._tcp')
        self.browser.connect('new-service', self.on_new_service)
        self.client = Avahi.Client()
        self.client.start()
        self.browser.attach(self.client)

    def on_service_found(self,
                         obj,
                         interface,
                         protocol,
                         name,
                         service_type,
                         domain,
                         hostname,
                         address,
                         port,
                         txt_records,
                         flags):
        '''Check to see if the found service was the companion app.'''
        if self.service_found_callback:
            self.service_found_callback(service_type, name, port)

    def on_new_service(self,
                       obj,
                       interface,
                       protocol,
                       name,
                       service_type,
                       domain,
                       flags):
        '''Found a new service, resolve it.'''
        self.resolver = Avahi.ServiceResolver.new(AVAHI_IF_UNSPEC,
                                                  AVAHI_PROTO_UNSPEC,
                                                  name,
                                                  service_type,
                                                  domain,
                                                  AVAHI_PROTO_UNSPEC,
                                                  Avahi.LookupFlags.GA_LOOKUP_NO_FLAGS)
        self.resolver.connect('found', self.on_service_found)
        self.resolver.attach(self.client)


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
        self.listener = None
        self.service = None

    def tearDown(self):
        '''Tear down the test case.'''
        self.listener = None
        self.service.stop()
        self.service = None

    @with_main_loop
    def test_services_get_established_on_startup(self, quit):
        '''Ensure that services are visible once started.'''
        def on_service_found(service_type, service_name, port):
            '''Called when a service is found.'''
            if service_name == 'EOSCompanionAppServiceTest':
                quit()

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1100)
        self.listener = AvahiServiceListener(on_service_found)

    @with_main_loop
    def test_second_service_gets_renamed(self, quit):
        '''Ensure that a second service gets renamed.'''
        def on_service_found(service_type, service_name, port):
            '''Called when a service is found.'''
            if service_name == 'EOSCompanionAppServiceTest (1)':
                quit()

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1110)
        self.service2 = CompanionAppService('EOSCompanionAppServiceTest', 1111)
        self.listener = AvahiServiceListener(on_service_found)

    @with_main_loop
    def test_make_connection_to_authenticate(self, quit):
        '''Ensure that we can authenticate with the serivce.'''
        def on_received_response(obj, result):
            '''Called when we receive a response from the server.'''
            stream = obj.send_finish(result)
            bytes = stream.read_bytes(8096, None)
            self.assertTrue(json.loads(bytes.get_data().decode())['status'] == 'ok')
            quit()

        def on_service_ready(obj):
            '''Called when a service is found.'''
            json_http_request_with_uuid('Some UUID',
                                        'http://localhost:1110/device_authenticate',
                                        {},
                                        on_received_response)

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1110)
        self.service.connect('services-established', on_service_ready)
        self.listener = AvahiServiceListener()

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

        def on_service_ready(obj):
            '''Called when a service is found.'''
            json_http_request_with_uuid('',
                                        'http://localhost:1110/device_authenticate',
                                        {},
                                        on_received_response)

        self.service = CompanionAppService('EOSCompanionAppServiceTest', 1110)
        self.service.connect('services-established', on_service_ready)
        self.listener = AvahiServiceListener()
