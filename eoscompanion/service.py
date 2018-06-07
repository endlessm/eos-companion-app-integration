# /eoscompanion/service.py
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
'''Service class for eoscompanion.'''

from gi.repository import (
    EosCompanionAppService,
    Gio,
    GObject
)

from .server import create_companion_app_webserver


def yield_monitors_over_changed_file_in_paths(paths, callback):
    '''Yield Gio.FileMonitor objects over each .changed file in :paths:.'''
    for path in paths:
        change_file = Gio.File.new_for_path(path).get_child('.changed')
        monitor = change_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        monitor.connect('changed', callback)
        yield monitor


def configure_drop_cache_on_changes(cache):
    '''Configure :cache: to be dropped when the Flatpak installation state changes.

    This creates a Gio.FileMonitor over each of the configured Flatpak
    installations on the system and drops all caches when they change.

    Note that we cannot use the Flatpak API here directly as we are running
    from within Flatpak. We are relying on an internal implementation
    detail, namely that Flatpak itself will update ".changed" in the
    installation directory on state changes.
    '''
    def _on_installation_changed(*args):
        '''Callback for when something changes.'''
        del args

        cache.clear()

    return list(
        yield_monitors_over_changed_file_in_paths(
            EosCompanionAppService.flatpak_install_dirs(),
            _on_installation_changed
        )
    )


class CompanionAppService(GObject.Object):
    '''A container object for the services.'''

    def __init__(self,
                 application,
                 port,
                 content_db_query,
                 *args,
                 middlewares=None,
                 **kwargs):
        '''Initialize the service and create webserver on port.

        :content_db_query: is a function satisfying the signature
                           def content_db_query(app_id: str,
                                                query: dict,
                                                callback: GAsyncReadyCallback)
                           which can be used by a route to query a content
                           database of some sort for an app_id.

        '''
        super().__init__(*args, **kwargs)

        # Create the server now and start listening.
        #
        # We want to listen right away as we'll probably be started by
        # socket activation
        self._cache = EosCompanionAppService.ManagedCache()
        self._monitors = configure_drop_cache_on_changes(self._cache)
        self._server = create_companion_app_webserver(application,
                                                      self._cache,
                                                      content_db_query,
                                                      middlewares=middlewares)
        EosCompanionAppService.soup_server_listen_on_sd_fd_or_port(self._server,
                                                                   port,
                                                                   0)

    def stop(self):
        '''Close all connections and de-initialise.

        The object is useless after this point.
        '''
        self._server.disconnect()
