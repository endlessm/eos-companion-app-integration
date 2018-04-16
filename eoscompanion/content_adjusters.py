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

import json

import os

import re

from urllib.parse import urlparse

from gi.repository import (
    Eknr,
    EosCompanionAppService,
    GLib,
    Gio
)

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


# The code below is a reimplementation of what is in libdmodel (which was
# not shared, since it is meant to be internal). This particular link-table-id
# is hardcoded into every shard and is the location of a dictionary mapping
# outgoing links to EKN IDs.
#
# See https://github.com/endlessm/libdmodel/blob/master/dmodel/dm-domain.c#L23
_LINK_TABLE_ID = '4dba9091495e8f277893e0d400e9e092f9f6f551'


def resolve_outgoing_link_to_internal_link(link_tables, outgoing_link):
    '''Use link_tables to resolve outgoing_link to an internal one.'''
    for table in link_tables:
        resolved = table.lookup_key(outgoing_link)

        if resolved is not None:
            return resolved

    return None


def link_tables_from_shards(shards):
    '''Look up all the link tables in the shards and yield them.'''
    for shard in shards:
        link_table_record = shard.find_record_by_hex_name(_LINK_TABLE_ID)

        if link_table_record is not None:
            yield link_table_record.data.load_as_dictionary()


def maybe_ekn_id_to_server_uri(ekn_uri, query):
    '''Convert an EKN URI (ekn:///id) to a URI that resolves on this server.

    If :ekn_uri: is None, return None.
    '''
    if ekn_uri is None:
        return None

    return rewrite_ekn_url(os.path.basename(urlparse(ekn_uri).path), query)


_MOBILE_WRAPPER_TEMPLATE_URI = (
    'resource:///com/endlessm/CompanionAppService/data/templates/mobile-article-wrapper.mst'
)


def render_mobile_wrapper(renderer,
                          app_id,
                          rendered_content,
                          metadata,
                          content_db_conn,
                          shards,
                          query,
                          callback):
    '''Render the page wrapper and initialize crosslinks.

    This is the final rendering step that EKN content needs to undergo before
    it becomes usable, at least before it leaves the server. This step
    initializes both a dictionary of metadata about the content and also a map
    of outgoing links to internal links. Then we inject some javascript which
    at browser-render time, rewrites the page to resolve all those links.
    '''
    def _on_queried_sets(error, result):
        '''Called when we finish querying set objects.'''
        if error is not None:
            callback(error, None)
            return

        _, set_objects = result
        content_metadata = {
            'title': metadata.get('title', ''),
            'published': metadata.get('published', ''),
            'authors': metadata.get('authors', []),
            'license': metadata.get('license', ''),
            'source': metadata.get('source', ''),
            'source_name': metadata.get('sourceName', ''),
            'originalURI': metadata.get('originalURI', ''),
            'sets': [
                {
                    'child_tags': set_object['child_tags'],
                    'id': set_object['id'],
                    'title': set_object['title'],
                    'tags': set_object['tags']
                }
                for set_object in set_objects
                if any([
                    tag in set_object['child_tags']
                    for tag in metadata.get('tags', [])
                    if not tag.startswith('Ekn')
                ])
            ]
        }

        # Now that we have everything, read the template and render it
        variables = GLib.Variant('a{sv}', {
            'css-files': GLib.Variant('as', [
                'clipboard.css',
                'share-actions.css'
            ]),
            'custom-css-files': GLib.Variant('as', []),
            'javascript-files': GLib.Variant('as', [
                'jquery-min.js',
                'crosslink.js'
            ]),
            'content': GLib.Variant('s', rendered_content),
            'crosslink-data': GLib.Variant('s', json.dumps(link_resolution_table)),
            'content-metadata': GLib.Variant('s', json.dumps(content_metadata))
        })

        try:
            template_file = Gio.File.new_for_uri(_MOBILE_WRAPPER_TEMPLATE_URI)
            rendered_page = renderer.render_mustache_document_from_file(template_file,
                                                                        variables)
        except GLib.Error as page_render_error:
            callback(page_render_error, None)
            return

        callback(None, rendered_page)

    link_tables = list(link_tables_from_shards(shards))
    link_resolution_table = [
        maybe_ekn_id_to_server_uri(
            resolve_outgoing_link_to_internal_link(link_tables, l),
            query
        )
        for l in metadata.get('outgoingLinks', [])
    ]

    content_db_conn.query(app_id,
                          query={
                              'tags-match-all': ['EknSetObject']
                          },
                          callback=_on_queried_sets)


def _html_content_adjuster_closure():
    '''Closure for the HTML content adjuster.'''
    renderer = Eknr.Renderer()

    def _html_content_adjuster(content_bytes,
                               query,
                               metadata,
                               content_db_conn,
                               shards,
                               callback):
        '''Adjust HTML content by rewriting all the embedded URLs.

        There will be images, video and links in the document, parse it
        and rewrite it so that the links all go to somewhere that can
        be resolved by the server.

        Right now the way that this is done is a total hack (regex), in future
        we might want to depend on beautifulsoup and use that instead.
        '''
        def _on_rendered_wrapper(error, rendered_page):
            '''Called when rendering the wrapper is complete.'''
            if error is not None:
                callback(error, None)
                return

            try:
                response_bytes = EosCompanionAppService.string_to_bytes(
                    pipeline(
                        rendered_page,
                        lambda content: _RE_EKN_URL_CAPTURE.sub(ekn_url_rewriter(query),
                                                                content),
                        lambda content: _RE_RESOURCE_URL_CAPTURE.sub(resource_url_rewriter(query),
                                                                     content)
                    )
                )
            except GLib.Error as render_bytes_error:
                callback(render_bytes_error, None)
                return

            callback(None, response_bytes)

        unrendered_html_string = EosCompanionAppService.bytes_to_string(content_bytes)
        if not metadata.get('isServerTemplated', False):
            rendered_content = renderer.render_legacy_content(
                unrendered_html_string,
                metadata.get('source', ''),
                metadata.get('sourceName', ''),
                metadata.get('originalURI', ''),
                metadata.get('license', ''),
                metadata.get('title', ''),
                show_title=True,
                use_scroll_manager=False
            )
        else:
            rendered_content = unrendered_html_string

        render_mobile_wrapper(renderer,
                              query['applicationId'],
                              rendered_content,
                              metadata,
                              content_db_conn,
                              shards,
                              query,
                              _on_rendered_wrapper)


    return _html_content_adjuster


CONTENT_TYPE_ADJUSTERS = {
    'text/html': _html_content_adjuster_closure()
}


def adjust_content(content_type,
                   content_bytes,
                   query,
                   metadata,
                   content_db_conn,
                   shards,
                   callback):
    '''Adjust content if necessary.'''
    if content_type in CONTENT_TYPE_ADJUSTERS:
        CONTENT_TYPE_ADJUSTERS[content_type](content_bytes,
                                             query,
                                             metadata,
                                             content_db_conn,
                                             shards,
                                             callback)
        return

    GLib.idle_add(lambda: callback(None, content_bytes))
