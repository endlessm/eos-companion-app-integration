# /eoscompanion/main.py
#
# Copyright (C) 2017, 2018 Endless Mobile, Inc.
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

import os
import sys

import gi

gi.require_version('Eknr', '0')
gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosMetrics', '0')
gi.require_version('EosShard', '0')


from gi.repository import (
    EosCompanionAppService,
    Gio,
    GLib,
)
from .constants import INACTIVITY_TIMEOUT
from .eknservices_bridge import EknServicesContentDbConnection
from .service import CompanionAppService
from .util import log


def _inhibit_auto_idle(connection, fd_callback):
    '''Use logind's D-Bus API to inhibit idle mode.

    Note that the inhibit lock is automatically released when the service
    shuts down.

    Once the method completes, fd_callback will be called with
    (error, fd). The passed fd will remain open until it is closed
    (for instance on process termination or on os.close()).
    '''
    def _on_inhibit_reply(src, result):
        '''Received a reply from logind, check if it succeeded.'''
        try:
            _, fd_list = src.call_with_unix_fd_list_finish(result)
        except GLib.Error as error:
            fd_callback(error, None)
            return

        # Now that we have the reply, get the passed fds and return
        # the first one to the caller through fd_callback
        fd_callback(None, fd_list.get(0))

    connection.call_with_unix_fd_list('org.freedesktop.login1',
                                      '/org/freedesktop/login1',
                                      'org.freedesktop.login1.Manager',
                                      'Inhibit',
                                      # XXX: These strings will need to be
                                      # localized at some point
                                      GLib.Variant('(ssss)',
                                                   ('sleep',
                                                    'Content Sharing',
                                                    'Content is being shared with another device',
                                                    'block')),
                                      GLib.VariantType('(h)'),
                                      Gio.DBusCallFlags.NONE,
                                      -1,
                                      None,
                                      None,
                                      _on_inhibit_reply)


class CompanionAppApplication(Gio.Application):
    '''Subclass of GApplication for controlling the companion app.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the application class.'''
        kwargs.update({
            'application_id': 'com.endlessm.CompanionAppService',
            'flags': Gio.ApplicationFlags.IS_SERVICE,
            'inactivity_timeout': INACTIVITY_TIMEOUT
        })
        super(CompanionAppApplication, self).__init__(*args, **kwargs)

        self._service = None
        self._inhibit_fd = None

    def do_startup(self):  # pylint: disable=arguments-differ
        '''Just print a message.'''
        Gio.Application.do_startup(self)

        if os.environ.get('EOS_COMPANION_APP_SERVICE_PERSIST', None):
            self.hold()

        Gio.bus_get(Gio.BusType.SYSTEM, None, self._on_got_system_bus)

    def _on_got_inhibit_fd(self, error, filedes):
        '''Report inhibit error or store returned fd.

        The returned fd is never closed explicitly, this process will
        hang on to it until it quits, where it will be closed implicitly
        and the inhibit lock released.
        '''
        if error is not None:
            log('Received error when attempting to take idle inhibit '
                'lock. Ensure that this user has sufficient permissions '
                '(eg, through org.freedesktop.login1.inhibit-block-idle). '
                'The error was: {}'.format(str(error)))
            return

        # Hang on to the fd so that we don't lose track of it, even though
        # this is strictly-speaking unused for now.
        #
        # pylint-disable: unused-attribute
        self._inhibit_fd = filedes

    def _on_got_system_bus(self, _, result):
        '''Called when we get a system D-Bus connection.'''
        try:
            connection = Gio.bus_get_finish(result)
        except GLib.Error as error:
            log('Error getting the system bus: {}'.format(str(error)))
            self.quit()
            return

        log('Got system d-bus connection')
        _inhibit_auto_idle(connection, self._on_got_inhibit_fd)

    def do_dbus_register(self, connection, object_path):  # pylint: disable=arguments-differ
        '''Invoked when we get a D-Bus connection.'''
        log('Got session d-bus connection at {path}'.format(path=object_path))
        self._service = CompanionAppService(self,
                                            1110,
                                            EknServicesContentDbConnection(connection))
        return Gio.Application.do_dbus_register(self,
                                                connection,
                                                object_path)

    def do_dbus_unregister(self, connection, object_path):  # pylint: disable=arguments-differ
        '''Invoked when we lose a D-Bus connection.'''
        log('Lost session d-bus connection at {path}'.format(path=object_path))
        return Gio.Application.do_dbus_unregister(self,
                                                  connection,
                                                  object_path)

    def do_activate(self):  # pylint: disable=arguments-differ
        '''Invoked when the application is activated.'''
        log('Activated')
        return Gio.Application.do_activate(self)


def main(args=None):
    '''Entry point function.

    Since we're often running from within flatpak, make sure to override
    XDG_DATA_DIRS to include the flatpak exports too, since they don't get
    included by default.

    We use GLib.setenv here, since os.environ is only visible to
    Python code, but setting a variable in os.environ does not actually
    update the 'environ' global variable on the C side.
    '''
    flatpak_export_share_dirs = [
        os.path.join(d, 'exports', 'share')
        for d in EosCompanionAppService.flatpak_install_dirs()
    ]
    GLib.setenv('XDG_DATA_DIRS',
                os.pathsep.join([
                    GLib.getenv('XDG_DATA_DIRS') or ''
                ] + flatpak_export_share_dirs), True)
    CompanionAppApplication().run(args or sys.argv)
