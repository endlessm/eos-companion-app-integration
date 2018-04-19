# /eoscompanion/format.py
#
# Copyright (C) 2018 Endless Mobile, Inc.
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
'''URI formatting functions for eoscompanion.'''

import urllib



def format_uri_with_querystring(base_uri, **params):
    '''Format the passed uri with the querystring params.'''
    return '{base_uri}?{params}'.format(base_uri=base_uri,
                                        params=urllib.parse.urlencode(params))


def format_app_icon_uri(icon_name, device_uuid):
    '''Format a uri to get an icon for an app.'''
    return format_uri_with_querystring(
        '/v1/application_icon',
        deviceUUID=device_uuid,
        iconName=icon_name
    )


def format_thumbnail_uri(application_id, thumbnail_uri, device_uuid):
    '''Format a uri to get an icon for an app.'''
    return format_uri_with_querystring(
        '/v1/content_data',
        deviceUUID=device_uuid,
        applicationId=application_id,
        contentId=urllib.parse.urlparse(thumbnail_uri).path[1:]
    )


def optional_format_thumbnail_uri(application_id, model, device_uuid):
    '''Format a uri to get an icon for an app if the model has a thumbnail.'''
    return (
        format_thumbnail_uri(application_id, model['thumbnail_uri'], device_uuid)
        if model.get('thumbnail_uri', None)
        else None
    )


def rewrite_ekn_url(content_id, query):
    '''If the URL is an EKN url, rewrite it to be server-relative.

    This causes the applicationId and deviceUUID to be included in
    the URL query-string.
    '''
    formatted = format_uri_with_querystring(
        '/v1/content_data',
        deviceUUID=query['deviceUUID'],
        applicationId=query['applicationId'],
        contentId=content_id
    )
    return formatted


def rewrite_resource_url(uri, query):
    '''If the URL is an internal resource url, rewrite it to be server-relative.

    This causes the deviceUUID to be included in
    the URL query-string and the resource path to be URI encoded.
    '''
    formatted = format_uri_with_querystring(
        '/v1/resource',
        deviceUUID=query['deviceUUID'],
        uri=uri
    )
    return formatted


def rewrite_license_url(license_name, query):
    '''If the URL is an internal license url, rewrite it to be server-relative.

    This causes the deviceUUID to be included in
    the URL query-string and the resource path to be URI encoded.
    '''
    formatted = format_uri_with_querystring(
        '/v1/license',
        deviceUUID=query['deviceUUID'],
        name=license_name
    )
    return formatted
