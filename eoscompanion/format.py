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

import os
import urllib


def parse_uri_path_basename(uri):
    '''Just get the basename of the last path component of a URI.'''
    return os.path.basename(urllib.parse.urlparse(uri).path)


def format_uri_with_querystring(base_uri, **params):
    '''Format the passed uri with the querystring params.'''
    return '{base_uri}?{params}'.format(base_uri=base_uri,
                                        params=urllib.parse.urlencode(params))


def format_app_icon_uri(version, icon_name, device_uuid):
    '''Format a uri to get an icon for an app.'''
    return format_uri_with_querystring(
        '/{version}/application_icon'.format(version=version),
        deviceUUID=device_uuid,
        iconName=icon_name
    )


def format_thumbnail_uri(version, application_id, thumbnail_uri, device_uuid):
    '''Format a uri to get an icon for an app.'''
    return format_uri_with_querystring(
        '/{version}/content_data'.format(version=version),
        deviceUUID=device_uuid,
        applicationId=application_id,
        contentId=parse_uri_path_basename(thumbnail_uri)
    )


def optional_format_thumbnail_uri(version, application_id, model, device_uuid):
    '''Format a uri to get an icon for an app if the model has a thumbnail.'''
    return (
        format_thumbnail_uri(version,
                             application_id,
                             model['thumbnail_uri'],
                             device_uuid)
        if model.get('thumbnail_uri', None)
        else None
    )


def format_content_data_uri(version, content_id, application_id, device_uuid):
    '''Format a /content_data URI.'''
    return format_uri_with_querystring(
        '/{version}/content_data'.format(version=version),
        deviceUUID=device_uuid,
        applicationId=application_id,
        contentId=content_id
    )


def rewrite_ekn_url(content_id, version, query):
    '''If the URL is an EKN url, rewrite it to be server-relative.

    This causes the applicationId and deviceUUID to be included in
    the URL query-string.
    '''
    return format_content_data_uri(version,
                                   content_id,
                                   query['applicationId'],
                                   query['deviceUUID'])


def rewrite_resource_url(uri, version, query):
    '''If the URL is an internal resource url, rewrite it to be server-relative.

    This causes the deviceUUID to be included in
    the URL query-string and the resource path to be URI encoded.
    '''
    formatted = format_uri_with_querystring(
        '/{version}/resource'.format(version=version),
        deviceUUID=query['deviceUUID'],
        uri=uri
    )
    return formatted


def rewrite_license_url(license_name, version, query):
    '''If the URL is an internal license url, rewrite it to be server-relative.

    This causes the deviceUUID to be included in
    the URL query-string and the resource path to be URI encoded.
    '''
    formatted = format_uri_with_querystring(
        '/{version}/license'.format(version=version),
        deviceUUID=query['deviceUUID'],
        name=license_name
    )
    return formatted
