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
    GObject
)

from .routes import create_companion_app_webserver


class CompanionAppService(GObject.Object):
    '''A container object for the services.'''

    def __init__(self, application, port, *args, **kwargs):
        '''Initialize the service and create webserver on port.'''
        super().__init__(*args, **kwargs)

        # Create the server now and start listening.
        #
        # We want to listen right away as we'll probably be started by
        # socket activation
        self._server = create_companion_app_webserver(application)
        EosCompanionAppService.soup_server_listen_on_sd_fd_or_port(self._server,
                                                                   port,
                                                                   0)

    def stop(self):
        '''Close all connections and de-initialise.

        The object is useless after this point.
        '''
        self._server.disconnect()
