# /eoscompanion/ekn_query.py
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
'''Functions to query an EKN database provider for content.'''

import urllib

from gi.repository import (
    EosCompanionAppService,
    GLib
)

from .applications_query import application_listing_from_app_info
from .format import (
    format_app_icon_uri,
    optional_format_thumbnail_uri
)

# This tag is used by everything that should end up on the homepage
_GLOBAL_SET_INDICATOR_TAG = ['EknHomePageTag']


def ascertain_application_sets_from_models(models,
                                           device_uuid,
                                           application_id,
                                           cancellable,
                                           done_callback):
    '''Pass application sets or an entry for the global set to callback.'''
    def _on_received_application_info(_, result):
        '''Called when we receive requested application info.'''
        try:
            listing = application_listing_from_app_info(
                EosCompanionAppService.finish_load_application_info(result)
            )
        except Exception as error:
            done_callback(error, None)
            return

        done_callback(None, [
            {
                'tags': _GLOBAL_SET_INDICATOR_TAG,
                'title': listing.display_name,
                'contentType': 'application/x-ekncontent-set',
                'thumbnail': format_app_icon_uri(listing.icon, device_uuid),
                'id': '',
                'global': True
            }
        ])

    try:
        application_sets_response = [
            {
                'tags': model['child_tags'],
                'title': model['title'],
                'contentType': 'application/x-ekncontent-set',
                'thumbnail': optional_format_thumbnail_uri(application_id,
                                                           model,
                                                           device_uuid),
                'id': urllib.parse.urlparse(model['id']).path[1:],
                'global': False
            }
            for model in models
        ]

        if application_sets_response:
            GLib.idle_add(done_callback, None, application_sets_response)
            return

        EosCompanionAppService.load_application_info(application_id,
                                                     cancellable=cancellable,
                                                     callback=_on_received_application_info)
    except Exception as error:
        GLib.idle_add(done_callback, error, None)
