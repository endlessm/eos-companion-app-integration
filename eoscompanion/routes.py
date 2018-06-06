# /eoscompanion/routes.py
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
'''Constructor for all routes.'''

from .core_routes import create_core_routes
from .v1_routes import create_companion_app_routes_v1
from .v2_routes import create_companion_app_routes_v2


def create_companion_app_routes(content_db_conn):
    '''Create routes and apply content_db_conn to them.'''
    routes = create_core_routes()
    routes.update(create_companion_app_routes_v1(content_db_conn))
    routes.update(create_companion_app_routes_v2(content_db_conn))
    return routes
