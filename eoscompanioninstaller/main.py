# /eoscompanioninstaller/main.py
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
'''Main executable entry point for eos-companion-app-offline-installer.'''

import logging
import os
import sys

import gi

gi.require_version('EosCompanionAppOfflineInstaller', '1.0')
gi.require_version('Gtk', '3.0')


from gi.repository import (
    EosCompanionAppOfflineInstaller,
    Gio,
    GLib,
    Gtk
)        


RESOURCE_PATH = '/com/endlessm/CompanionAppOfflineInstaller/data/installer/ui/main.ui'


def create_window_resources():
    '''Create the main window resources and builder.'''
    builder = Gtk.Builder.new_from_resource(RESOURCE_PATH)
    main_window = builder.get_object('installer-main-window')
    install_with_wifi_dialog = builder.get_object('installer-download-wifi-dialog')
    install_with_bluetooth_dialog = builder.get_object('installer-download-bluetooth-dialog')

    return builder, main_window, install_with_wifi_dialog, install_with_bluetooth_dialog


class CompanionAppOfflineInstallerApplication(Gtk.Application):
    '''Subclass of GtkApplication for controlling the companion app.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the application class.'''
        kwargs.update({
            'application_id': 'com.endlessm.CompanionAppService.OfflineInstaller'
        })
        super(CompanionAppOfflineInstallerApplication, self).__init__(*args, **kwargs)

        self.builder = None
        self.main_window = None
        self.install_with_wifi_dialog = None
        self.install_with_bluetooth_dialog = None

    def do_startup(self):  # pylint: disable=arguments-differ
        '''Just print a message.'''
        Gtk.Application.do_startup(self)
        logging.info('Starting up')

    def do_dbus_register(self, connection, object_path):  # pylint: disable=arguments-differ
        '''Invoked when we get a D-Bus connection.'''
        logging.info('Got session d-bus connection at %s', object_path)
        return Gtk.Application.do_dbus_register(self,
                                                connection,
                                                object_path)

    def do_dbus_unregister(self, connection, object_path):  # pylint: disable=arguments-differ
        '''Invoked when we lose a D-Bus connection.'''
        logging.warning('Lost session d-bus connection at %s', object_path)
        return Gtk.Application.do_dbus_unregister(self,
                                                  connection,
                                                  object_path)

    def do_activate(self):  # pylint: disable=arguments-differ
        '''Invoked when the application is activated.'''
        logging.info('Activated')

        if self.builder is None:
            (self.builder,
             self.main_window,
             self.install_with_wifi_dialog,
             self.install_with_bluetooth_dialog) = create_window_resources()

        result = Gtk.Application.do_activate(self)

        self.main_window.show_all()
        return result


def main(args=None):
    '''Entry point function.

    Since we're often running from within flatpak, make sure to override
    XDG_DATA_DIRS to include the flatpak exports too, since they don't get
    included by default.

    We use GLib.setenv here, since os.environ is only visible to
    Python code, but setting a variable in os.environ does not actually
    update the 'environ' global variable on the C side.
    '''
    logging.basicConfig(format='CompanionAppOfflineInstaller %(levelname)s: %(message)s',
                        level=logging.INFO)
    CompanionAppOfflineInstallerApplication().run(args or sys.argv)
