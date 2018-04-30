# /eoscompanion/license_content_adjuster.py
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
'''Implementation of Adjuster for License files.

The adjuster is a piece of output middleware that take an a stream
of license content and rewrites embedded URLs to be file:/// style
URIs relative to the licenses directory in eos-sdk.
'''

import os

import re

from gi.repository import (
    EosCompanionAppService,
    Gio,
    GLib
)

from .format import format_uri_with_querystring

_RE_RELATIVE_HTML_URL_CAPTURE = re.compile(r'"(?P<relative>\.\.[\.\/A-Za-z0-9-]+)"')
# Need to use a non-raw string here to get both double and single quotes
# pylint: disable=anomalous-backslash-in-string
_RE_CSS_URL_CAPTURE = re.compile("url\([\"']?(?P<path>[\.\/A-Za-z0-9-]+)[\"']?\)")


def rewrite_relative_url(relative, query, source_path):
    '''Rewrite the relative URL as a resource URL.'''
    file_uri = Gio.File.new_for_path(os.path.join(os.path.dirname(source_path),
                                                  relative)).get_uri()
    formatted = format_uri_with_querystring(
        '/v1/resource',
        deviceUUID=query['deviceUUID'],
        uri=file_uri,
        adjuster='license'
    )
    return formatted


def relative_html_url_rewriter(query, source_path):
    '''Higher order function to rewrite an embedded HTML URL based on query.

    This finds relative urls in a document and rewrites them as absolute
    paths based on their position relative to source_path.
    '''
    return lambda m: '"{}"'.format(rewrite_relative_url(m.group('relative'),
                                                        query,
                                                        source_path))


def relative_css_url_rewriter(query, source_path):
    '''Higher order function to rewrite an embedded CSS URL based on query.

    This finds relative urls in a document and rewrites them as absolute
    paths based on their position relative to source_path.
    '''
    return lambda m: 'url({})'.format(rewrite_relative_url(m.group('path'),
                                                           query,
                                                           source_path))


def _render_license_html_content(content_bytes, query, source_path):
    '''Render the HTML license content by rewriting all the URIs.'''
    unrendered_html_string = EosCompanionAppService.bytes_to_string(content_bytes)
    return EosCompanionAppService.string_to_bytes(
        _RE_RELATIVE_HTML_URL_CAPTURE.sub(
            relative_html_url_rewriter(query, source_path),
            unrendered_html_string
        )
    )


def _render_license_css_content(content_bytes, query, source_path):
    '''Render the CSS license content by rewriting all the URIs.'''
    unrendered_css_string = EosCompanionAppService.bytes_to_string(content_bytes)
    return EosCompanionAppService.string_to_bytes(
        _RE_CSS_URL_CAPTURE.sub(
            relative_css_url_rewriter(query, source_path),
            unrendered_css_string
        )
    )


_CONTENT_TYPE_DISPATCH = {
    'text/html': _render_license_html_content,
    'text/css': _render_license_css_content
}


def render_license_content_async(content_type,
                                 content_bytes,
                                 query,
                                 source_path,
                                 callback):
    '''Render the license content by rewriting all the URIs.'''
    try:
        response_bytes = _CONTENT_TYPE_DISPATCH[content_type](content_bytes,
                                                              query,
                                                              source_path)
    except GLib.Error as error:
        GLib.idle_add(lambda: callback(error, None))
        return

    GLib.idle_add(lambda: callback(None, response_bytes))


class LicenseContentAdjuster(object):
    '''An implementation of Adjuster for License Content routes.'''

    def __init__(self, source_path):
        '''Initialize this LicenseContentAdjuster with resources that it requires.'''
        super().__init__()
        self._source_path = source_path

    @staticmethod
    def create_from_resource_query(source_path, _):
        '''Create a LicenceContentAdjuster from a /resource query object.'''
        return LicenseContentAdjuster(source_path)

    @staticmethod
    def needs_adjustment(content_type):
        '''Returns True in every case as licenses always need adjustment.'''
        return content_type in _CONTENT_TYPE_DISPATCH.keys()

    def render_async(self, content_type, content_bytes, query, callback):
        '''Perform any rendering on the content asynchronously.'''
        render_license_content_async(content_type,
                                     content_bytes,
                                     query,
                                     self._source_path,
                                     callback)
