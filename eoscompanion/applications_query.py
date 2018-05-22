# /eoscompanion/applications_query.py
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
'''Functions to query installed applications on the system.'''

from collections import namedtuple

from gi.repository import (
    EosCompanionAppService,
    GLib,
)

ApplicationListing = namedtuple('ApplicationListing',
                                ('app_id display_name short_description '
                                 'icon language eknservices_name '
                                 'search_provider_name'))


def maybe_get_app_info_string(app_info, name):
    '''Conditionally get the locale-independent string for name.

    Return None if the operation fails due to the entry not being present
    in the app_info.
    '''
    try:
        return app_info.get_string(name)
    except GLib.Error:
        return None


def application_listing_from_app_info(app_info):
    '''Convert a EosCompanionAppServiceAppInfo app_info to an ApplicationListing.'''
    desktop_app_info = app_info.get_desktop_app_info()
    display_name = desktop_app_info.get_display_name()
    short_description = desktop_app_info.get_description()
    app_id = desktop_app_info.get_string('X-Flatpak')
    icon = desktop_app_info.get_string('Icon')
    eknservices_name = app_info.get_eknservices_name()
    search_provider_name = app_info.get_search_provider_name()

    # Fall back to using the last component of the
    # app name if that doesn't work
    language = (
        maybe_get_app_info_string(desktop_app_info,
                                  'X-Endless-Content-Language') or
        app_id.split('.')[-1]
    )

    return ApplicationListing(app_id,
                              display_name,
                              short_description,
                              icon,
                              language,
                              eknservices_name,
                              search_provider_name)


def list_all_applications(cancellable, callback):
    '''Convenience function to pass list of ApplicationListing to callback.'''
    def _callback(_, result):
        '''Callback function that gets called when we are done.'''
        try:
            infos = EosCompanionAppService.finish_list_application_infos(result)
        except GLib.Error as error:
            callback(error, None)
            return

        callback(None, [
            application_listing_from_app_info(app_info)
            for app_info in infos
        ])

    EosCompanionAppService.list_application_infos(cancellable, _callback)
