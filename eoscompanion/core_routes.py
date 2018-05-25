# /eoscompanion/core_routes.py
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
'''Unversioned route definitions for eos-companion-app-service.'''

from .constants import (
    SERVER_API_VERSION
)
from .responses import (
    html_response,
    json_response
)


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


def heartbeat_route(server, msg, *args):
    '''A no-op heartbeat route.

    All this does is keep the server alive by extending its inactivity
    timeout. It always returns the same response and takes no parameters. It
    should be invoked in the background if the client is in the foreground
    and does not want the server to go away.
    '''
    del server
    del args

    json_response(msg, {
        "status": "ok"
    })


def version_route(server, msg, *args):
    '''A route which just returns the current server version.

    The client also has a corresponding server API version number. If the
    client's version is higher, then the client should complain about
    the server needing to update the 'Endless Platform'. If the server's version
    is higher, the client should complain about needing to be updated from
    the Play Store.
    '''
    del server
    del args

    json_response(msg, {
        "status": "ok",
        "payload": {
            "version": SERVER_API_VERSION
        }
    })


def create_core_routes():
    '''Create the routes used for internal synchronization between app and service.'''
    return {
        '/': companion_app_server_root_route,
        '/heartbeat': heartbeat_route,
        '/version': version_route
    }
