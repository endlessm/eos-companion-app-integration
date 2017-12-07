# /eoscompanion/main.py
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
'''Main executable entry point for eos-companion-app-service.'''

import json
import re
import sys
import gi

gi.require_version('Avahi', '0.6')
gi.require_version('EosCompanionAppService', '1.0')

from gi.repository import Avahi, EosCompanionAppService, Gio, GLib, GObject, Soup


def serialize_error_as_json_object(domain, code, detail={}):
    '''Serialize a GLib.Error as a JSON object.'''
    return {
        'domain': GLib.quark_to_string(domain),
        'code': code.value_name,
        'detail': detail
    }


def json_response(msg, obj):
    '''Respond with a JSON object'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response(msg,
                                                     'application/json',
                                                     json.dumps(obj))


def html_response(msg, html):
    '''Respond with an HTML body.'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response(msg,
                                                     'text/html',
                                                     html)

def require_header(header):
    '''Require a header to be defined on the incoming message or raise.'''
    def decorator(handler):
        def middleware(server, msg, path, query, client):
            if not msg.request_headers.get_one(header):
                return json_response(msg, {
                    'status': 'error',
                    'error': serialize_error_as_json_object(
                        EosCompanionAppService.error_quark(),
                        EosCompanionAppService.Error.INVALID_REQUEST,
                        detail={
                            'missing_header': header
                        }
                    )
                })

            return handler(server, msg, path, query, client)
        return middleware
    return decorator


def companion_app_server_root_route(_, msg, *args):
    '''Not a documented route, just show the user somewhere more useful.'''
    del args

    html = '''
    <html>
        <body>
            <h1>Endless OS Companion App</h1>
            <p>This is the web-server for the Endless OS Companion App - connect
               to this computer on your Android device</p>
        </body>
    </html>
    '''
    html_response(msg, html)


@require_header('X-Endless-CompanionApp-UUID')
def companion_app_server_device_authenticate_route(_, msg, *args):
    '''Authorize the client.'''
    print('Would authorize client with id {id}'.format(
        id=msg.request_headers.get_one('X-Endless-CompanionApp-UUID'))
    )
    json_response(msg, {
        'status': 'ok',
        'error': None
    })


def create_companion_app_webserver():
    '''Create a HTTP server with companion app routes.'''
    server = Soup.Server()
    server.add_handler('/', companion_app_server_root_route)
    server.add_handler('/device_authenticate', companion_app_server_device_authenticate_route)
    return server


def revise_name(service_name):
    '''Revise the service name into something that won't collide.'''
    match = re.match('.*\((\d+)\)\s*$', service_name)

    if match:
        span = match.span(1)
        num = int(service_name[span[0]:span[1]])
        return service_name[:span[0]] + str(num + 1) + service_name[span[1]:]

    return '{name} (1)'.format(name=service_name)


class AvahiEntryGroupWrapper(Avahi.EntryGroup):
    '''Subclass of Avahi.EntryGroup with idempotent attach method.'''

    def __init__(self, *args, **kwargs):
        '''Initialise the application class.'''
        super(Avahi.EntryGroup, self).__init__(*args, **kwargs)
        self._attached = False

    def attach(self, client):
        '''Attach to client, but do nothing if already attached.

        Invariant is that we must have already been attached to the
        same client. It is a programmer error to try and attach to
        a different client.
        '''
        if not self._attached:
            super(AvahiEntryGroupWrapper, self).attach(client)
            self._attached = True


# Avahi-GObject does not define this constant anywhere, so we have to
# define ourselves
AVAHI_ERROR_LOCAL_SERVICE_NAME_COLLISION = -8


def register_services(group, service_name, port):
    '''Attempt to register services under the :service_name:.

    If that fails, revise the name and keep trying until it works, returning
    the final service name in use.
    '''
    group.reset()
    # See the documentation of this function, we cannot use
    # group.add_service_full since that is not introspectable
    #
    # https://github.com/lathiat/avahi/issues/156
    while True:
        try:
            EosCompanionAppService.add_avahi_service_to_entry_group(group,
                                                                    service_name,
                                                                    '_eoscompanion._tcp',
                                                                    None,
                                                                    None,
                                                                    port,
                                                                    'sam=australia')
            break
        except Exception as error:
            if error.matches(Avahi.error_quark(), AVAHI_ERROR_LOCAL_SERVICE_NAME_COLLISION):
                service_name = revise_name(service_name)
                print('Local name collision, changing name to "{}"'.format(service_name))
                continue

            raise error

    group.commit()
    return service_name


class CompanionAppService(GObject.Object):
    '''A container object for the services.'''

    def __init__(self, service_name, port, *args, **kwargs):
        '''Initialize the service, attach to Avahi.'''
        super().__init__(*args, **kwargs)

        self._service_name = service_name
        self._port = port
        self._client = Avahi.Client()
        self._group = AvahiEntryGroupWrapper()

        # Tricky - the state-changed signal only gets fired once, and only
        # once we call client.start(). However, we can only initialise
        # self._group once the client has actually started, so we need to
        # do that there are not here
        self._client.connect('state-changed', self.on_server_state_changed)
        self._client.start()

        self._group.connect('state-changed', self.on_entry_group_state_changed)

        # Create the server now, even if we don't start listening yet
        self._server = create_companion_app_webserver()

    def stop(self):
        '''Close all connections and de-initialise.

        The object is useless after this point.
        '''
        self._server.disconnect()

    @GObject.Signal(name='services-established')
    def signal_services_established(self):
        '''Default handler for services-established.'''
        print('Services established under name "{}"'.format(self._service_name), file=sys.stderr)

    @GObject.Signal(name='remote-name-collision')
    def signal_remote_name_collision(self):
        '''Default handler for services-established.'''
        print('Remote name collision, will try with name "{}"'.format(self._service_name), file=sys.stderr)

    @GObject.Signal(name='services-establish-fail')
    def signal_remote_name_collision(self):
        '''Default handler for remote-name-collision.'''
        print('Services failed to established', file=sys.stderr)

    def on_entry_group_state_changed(self, entry_group, state):
        '''Handle group state changes.'''
        if state == Avahi.EntryGroupState.GA_ENTRY_GROUP_STATE_ESTABLISHED:
            EosCompanionAppService.soup_server_listen_on_sd_fd_or_port(self._server,
                                                                       self._port,
                                                                       0)

            self.emit('services-established')
        # This is a typo in the avahi-glib API, looks like we are stuck
        # with it :(
        #
        # https://github.com/lathiat/avahi/issues/157
        elif state == Avahi.EntryGroupState.GA_ENTRY_GROUP_STATE_COLLISTION:
            self._service_name = register_services(self._group,
                                                   revise_name(self._service_name),
                                                   self._port)
            self.emit('remote-name-collision')
        elif state == Avahi.EntryGroupState.GA_ENTRY_GROUP_STATE_FAILURE:
            self.emit('services-establish-fail')

    def on_server_state_changed(self, service, state):
        '''Handle state changes on the server side.'''
        if state == Avahi.ClientState.GA_CLIENT_STATE_S_COLLISION:
            self._service_name = register_services(self._group,
                                                   revise_name(self._service_name),
                                                   self._port)
            self.emit('remote-name-collision')
        elif state == Avahi.ClientState.GA_CLIENT_STATE_S_RUNNING:
            print('Server running, registering services')

            # It is only safe to attach to the client now once the client
            # has actualy been set up. However, we can get to this point
            # multiple times so the wrapper class will silently prevent
            # attaching multiple times (which is an error)
            self._group.attach(self._client)

            self._service_name = register_services(self._group,
                                                   self._service_name,
                                                   self._port)

class CompanionAppApplication(Gio.Application):
    '''Subclass of GApplication for controlling the companion app.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the application class.'''
        kwargs.update({
            'application_id': 'com.endlessm.CompanionAppService',
            'flags': Gio.ApplicationFlags.IS_SERVICE
        })
        super(CompanionAppApplication, self).__init__(*args, **kwargs)

    def do_startup(self):
        '''Just print a message.'''
        Gio.Application.do_startup(self)

        self._service = CompanionAppService('EOSCompanionAppService', 1110)

    def do_dbus_register(self, connection, path):
        '''Invoked when we get a D-Bus connection.'''
        print('Got d-bus connection at {path}'.format(path=path))
        return Gio.Application.do_dbus_register(self, connection, path)

    def do_dbus_unregister(self, connection, path):
        '''Invoked when we lose a D-Bus connection.'''
        print('Lost d-bus connection at {path}'.format(path=path))
        return Gio.Application.do_dbus_unregister(self, connection, path)

    def do_activate(self):
        '''Invoked when the application is activated.'''
        print('Activated')
        return Gio.Application.do_activate(self)


def main(args=None):
    '''Entry point function.'''
    CompanionAppApplication().run(args or sys.argv)

