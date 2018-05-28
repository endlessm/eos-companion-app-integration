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
import math
import os
import sys

import gi

gi.require_version('EosCompanionAppOfflineInstaller', '1.0')
gi.require_version('GnomeBluetooth', '1.0')
gi.require_version('Gtk', '3.0')


from gi.repository import (
    EosCompanionAppOfflineInstaller,
    Gio,
    GLib,
    GnomeBluetooth,
    Gtk
)


from eoscompanion.functional import all_asynchronous_function_calls_closure


RESOURCE_PATH = '/com/endlessm/CompanionAppOfflineInstaller/data/installer/ui/main.ui'


def create_window_resources():
    '''Create the main window resources and builder.'''
    builder = Gtk.Builder.new_from_resource(RESOURCE_PATH)
    main_window = builder.get_object('installer-main-window')
    install_with_wifi_dialog = builder.get_object('installer-download-wifi-dialog')
    install_with_bluetooth_dialog = builder.get_object('installer-download-bluetooth-dialog')

    return builder, main_window, install_with_wifi_dialog, install_with_bluetooth_dialog


OBEX_SERVICE = "org.bluez.obex"
OBEX_PATH = "/org/bluez/obex"
OBEX_TRANSFER_IFACE = "org.bluez.obex.Transfer1"
OBEX_OPP_IFACE = "org.bluez.obex.ObjectPush1"
OBEX_CLIENT_IFACE = "org.bluez.obex.Client1"


def gio_callback_or_error_handler(source_object,
                                  async_func_name,
                                  async_func_finish_name,
                                  on_got_result_callback,
                                  error_handler_callback,
                                  *args):
    '''Call a GIO Async function on :source_object: and forward errors to error_handler_callback.'''
    def _callback(_, result):
        '''GAsyncReadyFunc compliant callback.'''
        try:
            unwrapped = getattr(source_object, async_func_finish_name)(result)
        except GLib.Error as error:
            error_handler_callback(error)
            return

        on_got_result_callback(unwrapped)

    getattr(source_object, async_func_name)(*args, _callback)


def create_dbus_proxy_async_or_error(connection,
                                     flags,
                                     interface_info,
                                     name,
                                     object_path,
                                     interface_name,
                                     cancellable,
                                     on_got_proxy_callback,
                                     error_handler_callback):
    '''Helper function to either get a D-Bus proxy asynchronously, or error out.'''
    gio_callback_or_error_handler(Gio.DBusProxy,
                                  'new',
                                  'new_finish',
                                  on_got_proxy_callback,
                                  error_handler_callback,
                                  connection,
                                  flags,
                                  interface_info,
                                  name,
                                  object_path,
                                  interface_name,
                                  cancellable)


def call_dbus_proxy_async_or_error(proxy,
                                   method,
                                   parameters,
                                   flags,
                                   timeout,
                                   cancellable,
                                   on_got_response_callback,
                                   error_handler_callback):
    '''Helper function to either call a D-Bus proxy asynchronously, or error out.'''
    gio_callback_or_error_handler(proxy,
                                  'call',
                                  'call_finish',
                                  on_got_response_callback,
                                  error_handler_callback,
                                  method,
                                  parameters,
                                  flags,
                                  timeout,
                                  cancellable)


def obex_push_file_to_addr(connection,
                           os_relative_filename,
                           addr,
                           cancellable,
                           progress_callback,
                           done_callback):
    '''Do the obex flow to push :os_relative_filename: to :addr:.'''
    def _handle_error(error):
        '''Internal error handler.'''
        done_callback(error, None)

    def _on_got_source_file_info(source_file_info):
        '''Callback for when we received the GFileInfo for the source filename.'''
        def _on_obex_transfer_props_changed(_,
                                            changed_properties,
                                            *args):
            '''Callback for when properties of the transfer change.'''
            del args

            unpacked_changed_properties = changed_properties.unpack()
            transfer_status = unpacked_changed_properties.get('Status', None)

            if transfer_status == 'complete':
                done_callback(None, 'complete')
            elif transfer_status == 'error':
                done_callback(None, 'error')

            if 'Transferred' in unpacked_changed_properties:
                transferred_bytes = unpacked_changed_properties['Transferred']
                fraction = transferred_bytes / source_file_size
                logging.info('Transferred %s bytes (%f%%)',
                             transferred_bytes,
                             math.trunc(fraction * 100))
                progress_callback(fraction)

        def _on_got_obex_transfer_proxy(transfer_proxy):
            '''Callback for when we get the OBEX transfer proxy.'''
            def _on_cancelled():
                '''Callback for when the transfer is cancelled.'''
                logging.info('OBEX transfer cancelled by user.')
                transfer_proxy.call_sync('Cancel',
                                         None,
                                         Gio.DBusCallFlags.NONE,
                                         -1,
                                         None)
                done_callback(None, 'cancelled')

            logging.info('Got OBEX transfer')
            transfer_proxy.connect('g-properties-changed',
                                   _on_obex_transfer_props_changed)
            cancellable.connect(_on_cancelled)

        def _on_created_obex_transfer(response):
            '''Callback for when the OBEX transfer is created.'''
            object_path, _ = response.unpack()

            logging.info('Created OBEX transfer at %s', object_path)
            create_dbus_proxy_async_or_error(connection,
                                             Gio.DBusProxyFlags.NONE,
                                             None,
                                             OBEX_SERVICE,
                                             object_path,
                                             OBEX_TRANSFER_IFACE,
                                             cancellable,
                                             _on_got_obex_transfer_proxy,
                                             _handle_error)

        def _on_got_obex_session_proxy(session_proxy):
            '''Callback for when we get the OBEX session proxy.'''
            logging.info('Got OBEX session')
            call_dbus_proxy_async_or_error(
                session_proxy,
                'SendFile',
                GLib.Variant('(s)', (os_relative_filename, )),
                Gio.DBusCallFlags.NONE,
                -1,
                cancellable,
                _on_created_obex_transfer,
                _handle_error
            )

        def _on_created_obex_session(response):
            '''Callback for when the OBEX session is created.'''
            object_path = response.unpack()[0]

            logging.info('Created OBEX session at %s', object_path)
            create_dbus_proxy_async_or_error(connection,
                                             Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
                                             Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                             None,
                                             OBEX_SERVICE,
                                             object_path,
                                             OBEX_OPP_IFACE,
                                             cancellable,
                                             _on_got_obex_session_proxy,
                                             _handle_error)

        def _on_got_obex_client(client):
            '''Callback for when we get the OBEX client.'''
            logging.info('Got OBEX client')
            call_dbus_proxy_async_or_error(
                client,
                'CreateSession',
                GLib.Variant('(sa{sv})', (addr, {
                    'Target': GLib.Variant('s', 'opp')
                })),
                Gio.DBusCallFlags.NONE,
                -1,
                cancellable,
                _on_created_obex_session,
                _handle_error
            )

        source_file_size = source_file_info.get_size()
        create_dbus_proxy_async_or_error(connection,
                                         Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
                                         Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                         None,
                                         OBEX_SERVICE,
                                         OBEX_PATH,
                                         OBEX_CLIENT_IFACE,
                                         cancellable,
                                         _on_got_obex_client,
                                         _handle_error)

    gio_callback_or_error_handler(Gio.File.new_for_path(os_relative_filename),
                                  'query_info_async',
                                  'query_info_finish',
                                  _on_got_source_file_info,
                                  _handle_error,
                                  Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                                  Gio.FileQueryInfoFlags.NONE,
                                  GLib.PRIORITY_DEFAULT,
                                  cancellable)


def enable_content_sharing_then(func, *args, **kwargs):
    '''Ensure that content sharing is enabled, then run func(*args, **kwargs).'''
    def _handle_error(error):
        '''Asynchronous error handler.'''
        logging.error('Error enabling content sharing: %s', error)

    def _on_instantiated_avahi_helper(error, result_bundle):
        '''Callback for once we got the AvahiHelper proxy.

        Ensure that content sharing is turned on, then show the
        "Install with WiFi dialog".
        '''
        def _on_content_sharing_enabled(_):
            '''Callback for once content sharing is enabled.'''
            logging.info('Content sharing is now enabled')
            func(*args, connection, avahi_helper_proxy, **kwargs)

            # All done. We'll leave content sharing in an enabled state
            # since the happy path is that the user installed the Companion App
            # and they now want to use it.

        if error is not None:
            _handle_error(error)
            return

        connection, avahi_helper_proxy = result_bundle
        call_dbus_proxy_async_or_error(avahi_helper_proxy,
                                       'EnterDiscoverableMode',
                                       None,
                                       Gio.DBusCallFlags.NONE,
                                       -1,
                                       None,
                                       _on_content_sharing_enabled,
                                       _handle_error)

    instantiate_avahi_helper_proxy(_on_instantiated_avahi_helper)


def run_install_bluetooth(install_with_bluetooth_dialog,
                          *args):
    '''Run the install-with-bluetooth dialog.'''
    del args

    install_with_bluetooth_dialog.run()
    install_with_bluetooth_dialog.hide()


# XXX: There seem to be some strange things going on here with closure
# bindings - having this as an internal function to setup_install_bluetooth
# causes a NameError when trying to invoke it from a callback
#
# pylint: disable=invalid-name
def update_send_button_state(bluetooth_chooser,
                             installer_download_bluetooth_progress,
                             installer_download_bluetooth_send_file_button):
    '''Make the 'send' button active if the bluetooth_chooser has a selected entry.'''
    selected_device = bluetooth_chooser.get_property('device-selected')
    installer_download_bluetooth_send_file_button.set_property(
        'sensitive',
        selected_device is not None
        and not installer_download_bluetooth_progress.get_property('visible')
    )


def update_progress_bar_fraction(progress_bar, fraction):
    '''Set the fraction and the text for the progress bar.'''
    progress_bar.set_property('fraction', fraction)
    progress_bar.set_property(
        'text',
        '{pc}%'.format(pc=math.trunc(fraction * 100))
    )


def setup_install_bluetooth(connection,
                            builder,
                            install_with_bluetooth_dialog):
    '''Set up the install-with-bluetooth buttons.'''
    cancellable = None

    # pylint: disable=invalid-name
    def setup_selection_widgets(bluetooth_chooser,
                                installer_download_bluetooth_progress):
        '''Set the initial state of the bluetooth send widgets.'''
        bluetooth_chooser.set_property('sensitive', True)
        installer_download_bluetooth_progress.hide()
        update_progress_bar_fraction(installer_download_bluetooth_progress, 0)
        update_send_button_state(bluetooth_chooser,
                                 installer_download_bluetooth_progress,
                                 installer_download_bluetooth_send_file_button)

    def _on_transfer_complete(error, transfer_status):
        '''Run when the transfer finishes.

        In all cases, reset the selection widgets so that we can do another
        transfer. On success, hide the dialog, otherwise, keep it around.
        '''
        setup_selection_widgets(bluetooth_chooser,
                                installer_download_bluetooth_progress)

        if error is not None:
            logging.error('Error occurred: %s', error)
            return

        logging.info('Transfer completed with status: %s', transfer_status)

        if transfer_status in ('complete', 'cancelled'):
            install_with_bluetooth_dialog.response(Gtk.ResponseType.NONE)
            return

    def _on_transfer_progress(fraction):
        '''Callback for when we get progress information.

        :fraction: is a floating point number between 0 and 1.
        '''
        update_progress_bar_fraction(installer_download_bluetooth_progress,
                                     fraction)

    def _on_bluetooth_cancel_clicked(*args):
        '''Callback for when the cancel button is pressed.

        Fire the cancellable which will cancel any transfers in progress.
        '''
        del args

        if cancellable is not None:
            cancellable.cancel()

        install_with_bluetooth_dialog.response(Gtk.ResponseType.CANCEL)

    # pylint: disable=invalid-name
    def _on_bluetooth_send_clicked(bluetooth_chooser,
                                   installer_download_bluetooth_send_file_button,
                                   installer_download_bluetooth_progress):
        '''Callback for when the Send button is clicked.'''
        nonlocal cancellable

        # Reset the cancellable state by creating a new one
        cancellable = Gio.Cancellable()

        bluetooth_chooser.set_property('sensitive', False)
        installer_download_bluetooth_send_file_button.set_property('sensitive', False)
        installer_download_bluetooth_progress.show()
        obex_push_file_to_addr(
            connection,
            os.path.join('/',
                         'var',
                         'lib',
                         'flatpak',
                         'app',
                         'com.endlessm.CompanionAppService',
                         'current',
                         'active',
                         'files',
                         'share',
                         'apk',
                         'com.endlessm.eoscompanion.apk'),
            bluetooth_chooser.get_property('device-selected'),
            cancellable,
            _on_transfer_progress,
            _on_transfer_complete
        )


    # pylint: disable=line-too-long,invalid-name
    installer_send_with_bluetooth_button = builder.get_object('installer-send-with-bluetooth-button')

    # pylint: disable=line-too-long,invalid-name
    installer_download_bluetooth_send_file_button = builder.get_object('installer-download-bluetooth-send-file-button')
    # pylint: disable=line-too-long,invalid-name
    installer_download_bluetooth_cancel_button = builder.get_object('installer-download-bluetooth-cancel-button')
    # pylint: disable=line-too-long,invalid-name
    installer_download_bluetooth_progress = builder.get_object('installer-download-bluetooth-progress')
    installer_bluetooth_chooser_box = builder.get_object('installer-bluetooth-chooser-box')

    installer_send_with_bluetooth_button.connect(
        'clicked',
        lambda _: enable_content_sharing_then(
            run_install_bluetooth,
            install_with_bluetooth_dialog
        )
    )
    installer_download_bluetooth_send_file_button.connect(
        'clicked',
        lambda _: _on_bluetooth_send_clicked(bluetooth_chooser,
                                             installer_download_bluetooth_send_file_button,
                                             installer_download_bluetooth_progress)
    )
    installer_download_bluetooth_cancel_button.connect('clicked',
                                                       _on_bluetooth_cancel_clicked)

    bluetooth_chooser = GnomeBluetooth.Chooser(device_type_filter=GnomeBluetooth.Type.PHONE,
                                               hexpand=True,
                                               show_searching=True,
                                               show_device_category=False,
                                               show_device_type=False,
                                               show_device_type_column=False)
    bluetooth_chooser.start_discovery()
    bluetooth_chooser.show()
    bluetooth_chooser.connect(
        'selected-device-activated',
        lambda _, __: _on_bluetooth_send_clicked(bluetooth_chooser,
                                                 installer_download_bluetooth_send_file_button,
                                                 installer_download_bluetooth_progress)
    )
    bluetooth_chooser.connect(
        'selected-device-changed',
        lambda _, __: update_send_button_state(bluetooth_chooser,
                                               installer_download_bluetooth_progress,
                                               installer_download_bluetooth_send_file_button)
    )

    installer_bluetooth_chooser_box.pack_start(bluetooth_chooser, True, True, 0)
    setup_selection_widgets(bluetooth_chooser,
                            installer_download_bluetooth_progress)


COMPANION_APP_SERVICE_AVAHI_HELPER_NAME = 'com.endlessm.CompanionAppServiceAvahiHelper'
COMPANION_APP_SERVICE_AVAHI_HELPER_OBJECT_PATH = '/com/endlessm/CompanionAppServiceAvahiHelper'
COMPANION_APP_SERVICE_AVAHI_HELPER_IFACE = 'com.endlessm.CompanionApp.AvahiHelper'


def instantiate_avahi_helper_proxy(callback):
    '''Get a system D-Bus connection and instatiate the AvahiHelper proxy.'''
    def _handle_error(error):
        '''Handle asynchronous errors.'''
        callback(error, None)

    def _on_got_system_dbus_connection(connection):
        '''Callback for when we get a system D-Bus connection.'''
        def _on_got_proxy(avahi_helper_proxy):
            '''Callback for when we get the AvahiHelper proxy.'''
            callback(None, (connection, avahi_helper_proxy))

        create_dbus_proxy_async_or_error(connection,
                                         Gio.DBusProxyFlags.NONE,
                                         None,
                                         COMPANION_APP_SERVICE_AVAHI_HELPER_NAME,
                                         COMPANION_APP_SERVICE_AVAHI_HELPER_OBJECT_PATH,
                                         COMPANION_APP_SERVICE_AVAHI_HELPER_IFACE,
                                         None,
                                         _on_got_proxy,
                                         _handle_error)


    gio_callback_or_error_handler(Gio,
                                  'bus_get',
                                  'bus_get_finish',
                                  _on_got_system_dbus_connection,
                                  _handle_error,
                                  Gio.BusType.SYSTEM,
                                  None)


NETWORK_MANAGER_NAME = 'org.freedesktop.NetworkManager'
NETWORK_MANAGER_OBJECT_PATH = '/org/freedesktop/NetworkManager'
NETWORK_MANAGER_IFACE = 'org.freedesktop.NetworkManager'
NETWORK_MANAGER_CONNECTION_ACTIVE_IFACE = 'org.freedesktop.NetworkManager.Connection.Active'
NETWORK_MANAGER_IP4CONFIG_IFACE = 'org.freedesktop.NetworkManager.IP4Config'
PERMISSIBLE_CONNECTION_TYPES = ('802-3-ethernet', '802-11-wireless')


# pylint: disable=invalid-name
def run_install_wifi(install_with_wifi_dialog,
                     installer_send_with_wifi_download_qr_code_image,
                     installer_send_with_wifi_download_url,
                     installer_send_with_wifi_info,
                     installer_send_with_wifi_no_network,
                     system_bus_connection,
                     *args):
    '''Detect network settings, run the install-with-wifi dialog, then hide it once done.'''
    del args

    def _handle_network_detection_error(error):
        '''Handle async errors.'''
        logging.error('Error detecting network settings: %s', error)

    def _show_dialog():
        '''Show the "Install with Wi-Fi" dialog based on how it was configured.'''
        install_with_wifi_dialog.run()
        install_with_wifi_dialog.hide()

    def _handle_got_local_network_ip(ipv4_address):
        '''Show URL that the user should connect to based on their IP.'''
        url = 'http://{ipv4_address}:1110/get'.format(ipv4_address=ipv4_address)

        try:
            installer_send_with_wifi_download_qr_code_image.set_from_surface(
                EosCompanionAppOfflineInstaller.generate_qr_code_surface(url,
                                                                         QR_CODE_WIDTH)
            )
        except GLib.Error as error:
            logging.error('Error generating QR code for wifi installer: %s', error)

        installer_send_with_wifi_download_url.show()
        installer_send_with_wifi_info.show()
        installer_send_with_wifi_no_network.hide()
        installer_send_with_wifi_download_url.set_markup(
            '<a href="{url}">{url}</a>'.format(url=url)
        )
        _show_dialog()

    def _handle_no_networks_available():
        '''Tell the user that there are no active connections and to configure networking.'''
        # pylint: disable=line-too-long
        installer_send_with_wifi_download_qr_code_image.set_from_icon_name(
            'network-wireless-offline-symbolic',
            Gtk.IconSize.DIALOG
        )
        installer_send_with_wifi_download_url.hide()
        installer_send_with_wifi_info.hide()
        installer_send_with_wifi_no_network.show()
        _show_dialog()

    def _on_created_network_manager_proxy(nm_proxy):
        '''Callback for when we create the NetworkManager proxy.'''
        def _handle_error_getting_connection_proxy(error):
            '''Handle error getting a connection proxy.

            These errors are non-fatal, but we should still report them.
            '''
            logging.error('Error getting proxy for an active connection: %s', error)

        def _on_got_ipv4_config_proxy_for_selected_connection(ipv4_config_proxy):
            '''Callback for when we get the IPV4Config object.'''
            _handle_got_local_network_ip(
                ipv4_config_proxy.get_cached_property('AddressData').unpack()[0]['address']
            )

        def _on_got_all_active_connection_proxies(active_connection_proxies):
            '''Check all the active connections and filter for anything that is a local connection.

            Use the default one if it is there, otherwise use the first
            local one that is available

            If there are no connections, complain.
            '''
            successfully_created_proxies = [
                p for error, p in active_connection_proxies
                if error is None
            ]
            errors = [
                error for error, p in active_connection_proxies
                if error is not None
            ]

            for error in errors:
                _handle_error_getting_connection_proxy(error)

            candidate_proxies = [
                p for p in successfully_created_proxies
                if p.get_cached_property('Type').unpack() in PERMISSIBLE_CONNECTION_TYPES
            ]

            if not candidate_proxies:
                _handle_no_networks_available()
                return

            try:
                selected_active_connection_proxy = [ # pylint: disable=invalid-name
                    p for p in candidate_proxies
                    if p.get_cached_property('Default') is True
                ][0]
            except IndexError:
                selected_active_connection_proxy = candidate_proxies[0] # pylint: disable=invalid-name

            create_dbus_proxy_async_or_error(system_bus_connection,
                                             Gio.DBusProxyFlags.NONE,
                                             None,
                                             NETWORK_MANAGER_NAME,
                                             selected_active_connection_proxy.get_cached_property(
                                                 'Ip4Config'
                                             ).unpack(),
                                             NETWORK_MANAGER_IP4CONFIG_IFACE,
                                             None,
                                             _on_got_ipv4_config_proxy_for_selected_connection,
                                             _handle_network_detection_error)

        def _get_connection_proxy_for_object_path(object_path):
            '''Create function to asynchronously get connection proxy for object_path.'''
            def _call(callback):
                '''Asynchronously get the connection proxy

                Pass a tuple of (error, result) to callback, which will enum
                up in a list that gets enumerated later to check the results.
                '''
                create_dbus_proxy_async_or_error(system_bus_connection,
                                                 Gio.DBusProxyFlags.NONE,
                                                 None,
                                                 NETWORK_MANAGER_NAME,
                                                 object_path,
                                                 NETWORK_MANAGER_CONNECTION_ACTIVE_IFACE,
                                                 None,
                                                 lambda p: callback(None, p),
                                                 lambda e: callback(e, None))

            return _call

        active_connection_object_paths = nm_proxy.get_cached_property('ActiveConnections').unpack()

        # No active connections - tell the user to configure their network
        # settings, then come back.
        if not active_connection_object_paths:
            _handle_no_networks_available()
            return

        all_asynchronous_function_calls_closure([
            _get_connection_proxy_for_object_path(active_connection_object_path)
            for active_connection_object_path in active_connection_object_paths
        ], _on_got_all_active_connection_proxies)

    create_dbus_proxy_async_or_error(system_bus_connection,
                                     Gio.DBusProxyFlags.NONE,
                                     None,
                                     NETWORK_MANAGER_NAME,
                                     NETWORK_MANAGER_OBJECT_PATH,
                                     NETWORK_MANAGER_IFACE,
                                     None,
                                     _on_created_network_manager_proxy,
                                     _handle_network_detection_error)


QR_CODE_WIDTH = 128


def setup_install_wifi(builder,
                       install_with_wifi_dialog):
    '''Set up the install-with-wifi buttons.'''
    # pylint: disable=line-too-long
    installer_send_with_wifi_button = builder.get_object('installer-send-with-wifi-button')
    # pylint: disable=line-too-long,invalid-name
    installer_send_with_wifi_download_qr_code_image = builder.get_object('installer-send-with-wifi-download-qr-code-image')
    installer_send_with_wifi_info = builder.get_object('installer-send-with-wifi-info')
    # pylint: disable=invalid-name
    installer_send_with_wifi_no_network = builder.get_object('installer-send-with-wifi-no-network')
    # pylint: disable=invalid-name
    installer_send_with_wifi_download_url = builder.get_object('installer-send-with-wifi-download-url')

    # pylint: disable=line-too-long
    installer_send_with_wifi_button.connect(
        'clicked',
        lambda _: enable_content_sharing_then(
            run_install_wifi,
            install_with_wifi_dialog,
            installer_send_with_wifi_download_qr_code_image,
            installer_send_with_wifi_download_url,
            installer_send_with_wifi_info,
            installer_send_with_wifi_no_network
        )
    )


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
        self.add_window(self.main_window)
        self.add_window(self.install_with_wifi_dialog)
        self.add_window(self.install_with_bluetooth_dialog)

        setup_install_bluetooth(self.get_dbus_connection(),
                                self.builder,
                                self.install_with_bluetooth_dialog)
        setup_install_wifi(self.builder,
                           self.install_with_wifi_dialog)

        return result


def main(args=None):
    '''Entry point function.'''
    logging.basicConfig(format='CompanionAppOfflineInstaller %(levelname)s: %(message)s',
                        level=logging.INFO)

    # Hack to cause the resources to get loaded
    EosCompanionAppOfflineInstaller.init()
    CompanionAppOfflineInstallerApplication().run(args or sys.argv)
