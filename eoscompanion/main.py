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

import sys

import gi

gi.require_version('Avahi', '0.6')
gi.require_version('EosCompanionAppService', '1.0')

from gi.repository import Avahi, EosCompanionAppService, GLib, Gio


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


class CompanionAppApplication(Gio.Application):
    '''Subclass of GApplication for controlling the companion app.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the application class.'''
        self._service_name = 'EOSCompanionAppService'
        kwargs.update({
            'application_id': 'com.endlessm.CompanionAppService',
            'flags': Gio.Application.IS_SERVICE
        })
        super(CompanionAppApplication, self).__init__(*args, **kwargs)

    def on_entry_group_state_changed(self, entry_group, state):
        '''Handle group state changes.'''
        if state == Avahi.EntryGroupState.GA_ENTRY_GROUP_STATE_ESTABLISHED:
            print('Services established')
        elif state == Avahi.EntryGroupState.GA_ENTRY_GROUP_STATE_FAILURE:
            print('Services failed to established')

    def on_server_state_changed(self, service, state):
        '''Handle state changes on the server side.'''
        print('Server state changed to '.format(state))
        if state == Avahi.ClientState.GA_CLIENT_STATE_S_COLLISION:
            print('Server collision, pick a different name')
            self.group.reset()
        elif state == Avahi.ClientState.GA_CLIENT_STATE_S_RUNNING:
            print('Server running, registering services')

            # It is only safe to attach to the client now once the client
            # has actualy been set up. However, we can get to this point
            # multiple times so the wrapper class will silently prevent
            # attaching multiple times (which is an error)
            self.group.attach(self.client)

            # See the documentation of this function, we cannot use
            # group.add_service_full since that is not introspectable
            #
            # https://github.com/lathiat/avahi/issues/156
            EosCompanionAppService.add_avahi_service_to_entry_group(self.group,
                                                                    'EOSCompanionApp',
                                                                    '_eoscompanion._tcp',
                                                                    None,
                                                                    None,
                                                                    1110,
                                                                    'sam=australia')
            self.group.commit()

    def do_startup(self):
        '''Just print a message.'''
        Gio.Application.do_startup(self)

        # Stay in memory for a little while
        self.hold()

        self.client = Avahi.Client()
        self.group = AvahiEntryGroupWrapper()

        # Tricky - the state-changed signal only gets fired once, and only
        # once we call client.start(). However, we can only initialise
        # self.group once the client has actually started, so we need to
        # do that there are not here
        self.client.connect('state-changed', self.on_server_state_changed)
        self.client.start()

        self.group.connect('state-changed', self.on_entry_group_state_changed)

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

