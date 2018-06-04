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

import logging

from gi.repository import (
    EosCompanionAppService,
    GLib,
    Gio,
    Soup
)

from .constants import (
    SERVER_API_VERSION
)
from .content_streaming import get_file_size_and_stream
from .middlewares import record_metric
from .responses import (
    html_response,
    json_response,
    serialize_error_as_json_object
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


APK_PATH = '/app/share/apk/com.endlessm.eoscompanion.apk'


@record_metric('7be59566-2b23-408a-acf6-91490fc1df1c')
def companion_app_server_get_app_route(server,
                                       msg,
                                       path,
                                       query,
                                       context):
    '''A route which offers a bundled APK file for download.

    The APK file is bundled with the server is not guaranteed to be the most
    up to date but should at least be compatible with the current server API
    version.

    It should be offered to download with the appropriate headers set
    such that it is saved with an appropriate filename.
    '''
    del path
    del query

    def on_splice_finished(src, result):
        '''Callback for when we are done splicing.'''
        nonlocal msg

        try:
            src.splice_finish(result)
        except GLib.Error as splice_error:
            # Can't really do much here except log server side
            logging.debug(
                'Splice operation on file failed: %s', splice_error
            )

        # In every case, we must mark the message as finished
        # so that 'finished' signal listeners get invoked
        # (important to ensure that the application hold count
        # goes down!)
        msg.finished()

        # FIXME: This looks strange, but it is very important. It seems
        # as though accessing `msg` above creates a cyclic reference
        # since msg itself is an argument to the outer function
        # and we reference it in the inner function, but the inner
        # function is referenced by the outer function.
        #
        # Unfortunately, failure to finalize this object is a critical
        # failure for us, since the finalize handler does
        # things like closing sockets which we only have a finite
        # pool of. There is no other way to close those sockets
        # from the libsoup side. Setting this object to None
        # breaks the reference cycle and allows the object to
        # be finalized.
        msg = None
        return

    def _on_got_file_size_and_stream(error, details):
        '''Callback for when we have the file size and stream.

        We can now respond to the request by splicing the stream after setting
        the content-type.
        '''
        def on_wrote_headers(_):
            '''Callback when headers are written.'''
            stream = context.steal_connection()
            ostream = stream.get_output_stream()
            ostream.splice_async(istream,
                                 Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
                                 GLib.PRIORITY_DEFAULT,
                                 msg.cancellable,
                                 on_splice_finished)

        if error != None:
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.FAILED,
                    detail={
                        'message': str(error)
                    }
                )
            })
            server.unpause_message(msg)
            return

        istream, length = details
        response_headers = msg.get_property('response-headers')
        response_headers.set_content_length(length)
        response_headers.set_content_type('application/vnd.android.package-archive')
        response_headers.set_content_disposition('attachment', {
            'filename': 'Endless Companion App.apk'
        })
        msg.set_status(Soup.Status.OK)

        msg.connect('wrote-headers', on_wrote_headers)
        server.unpause_message(msg)

    get_file_size_and_stream(Gio.File.new_for_path(APK_PATH),
                             msg.cancellable,
                             _on_got_file_size_and_stream)
    server.pause_message(msg)


def create_core_routes():
    '''Create the routes used for internal synchronization between app and service.'''
    return {
        '/': companion_app_server_root_route,
        '/get': companion_app_server_get_app_route,
        '/heartbeat': heartbeat_route,
        '/version': version_route
    }
