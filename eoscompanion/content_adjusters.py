# /eoscompanion/content_adjusters.py
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
'''Content adjustment handling functions.'''

import re

from gi.repository import Eknr, EosCompanionAppService

from .format import (
    rewrite_ekn_url,
    rewrite_resource_url
)

_RE_EKN_URL_CAPTURE = re.compile(r'"ekn\:\/\/[a-z0-9\-_\.\\\/]*\/(?P<id>[a-z0-9]+)"')
_RE_RESOURCE_URL_CAPTURE = re.compile(r'"(?P<uri>(?:resource|file)\:\/\/[A-Za-z0-9\/\-\._]+)"')


def ekn_url_rewriter(query):
    '''Higher order function to rewrite a URL based on query.'''
    return lambda m: '"{}"'.format(rewrite_ekn_url(m.group('id'), query))


def resource_url_rewriter(query):
    '''Higher order function to rewrite a URL based on query.'''
    return lambda m: '"{}"'.format(rewrite_resource_url(m.group('uri'), query))


def pipeline(src, *funcs):
    '''Apply each function in funcs to src, in sequence.'''
    output = src

    for func in funcs:
        output = func(output)

    return output


def _html_content_adjuster_closure():
    '''Closure for the HTML content adjuster.'''
    renderer = Eknr.Renderer()

    def _html_content_adjuster(content_bytes, query, metadata):
        '''Adjust HTML content by rewriting all the embedded URLs.

        There will be images, video and links in the document, parse it
        and rewrite it so that the links all go to somewhere that can
        be resolved by the server.

        Right now the way that this is done is a total hack (regex), in future
        we might want to depend on beautifulsoup and use that instead.
        '''
        unrendered_html_string = EosCompanionAppService.bytes_to_string(content_bytes)
        if not metadata.get('isServerTemplated', False):
            rendered_content = renderer.render_legacy_content(
                unrendered_html_string,
                metadata.get('source', ''),
                metadata.get('sourceName',
                             ''),
                metadata.get('originalURI',
                             ''),
                metadata.get('license',
                             ''),
                metadata.get('title',
                             ''),
                show_title=True,
                use_scroll_manager=False
            )
        else:
            rendered_content = unrendered_html_string

        return EosCompanionAppService.string_to_bytes(
            pipeline(rendered_content,
                     lambda content: _RE_EKN_URL_CAPTURE.sub(ekn_url_rewriter(query),
                                                             content),
                     lambda content: _RE_RESOURCE_URL_CAPTURE.sub(resource_url_rewriter(query),
                                                                  content))
        )

    return _html_content_adjuster


CONTENT_TYPE_ADJUSTERS = {
    'text/html': _html_content_adjuster_closure()
}


def adjust_content(content_type, content_bytes, query, metadata):
    '''Adjust content if necessary.'''
    if content_type in CONTENT_TYPE_ADJUSTERS:
        return CONTENT_TYPE_ADJUSTERS[content_type](content_bytes,
                                                    query,
                                                    metadata)

    return content_bytes
