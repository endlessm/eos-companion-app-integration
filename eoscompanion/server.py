# /eoscompanion/server.py
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
'''Server constructor func for eoscompanion.'''

import logging

from gi.repository import Soup

from .middlewares import (
    application_hold_middleware,
    compose_middlewares,
    cancellability_middleware,
    handle_404_middleware
)
from .routes import create_companion_app_routes

def create_companion_app_webserver(application, content_db_conn):
    '''Create a HTTP server with companion app routes.'''
    def _on_request_aborted(server, msg, *args):
        '''Signal handler for when a request is aborted.

        We'll look at the msg here and if there is an attached cancellable
        put there by cancellability_middleware then we can cancel it now.
        '''
        del server
        del args

        cancellable = getattr(msg, 'cancellable', None)

        if cancellable is None:
            logging.debug('Message aborted without a cancellable')
            return

        cancellable.cancel()


    server = Soup.Server()
    for path, handler in create_companion_app_routes(content_db_conn).items():
        server.add_handler(
            path,
            compose_middlewares(cancellability_middleware,
                                handle_404_middleware(path),
                                application_hold_middleware(application),
                                handler)
        )

    server.connect('request-aborted', _on_request_aborted)
    return server
