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
    rewrite_ekn_url
)

_RE_EKN_URL_CAPTURE = re.compile(r'"ekn\:\/\/\/(?P<id>[a-z0-9]+)"')


def ekn_url_rewriter(query):
    '''Higher order function to rewrite a URL based on query.'''
    return lambda m: '"{}"'.format(rewrite_ekn_url(m.group('id'), query))


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
        print(unrendered_html_string,
                                                   metadata.get('isServerTemplated',
                                                                False),
                                                   metadata.get('source'),
                                                   metadata.get('sourceName'),
                                                   metadata.get('originalURI'),
                                                   metadata.get('license'),
                                                   metadata.get('title'))
        rendered_content = renderer.render_content(unrendered_html_string,
                                                   metadata.get('isServerTemplated',
                                                                False),
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
                                                   use_scroll_manager=False)

        return EosCompanionAppService.string_to_bytes(
            _RE_EKN_URL_CAPTURE.sub(ekn_url_rewriter(query), rendered_content)
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
