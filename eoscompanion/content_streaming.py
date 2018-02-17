# /eoscompanion/content_streaming.py
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
'''Content streaming functions.

These functions take a raw content stream and either adjust it or
set the right headers so that it will be streamed properly.
'''

from gi.repository import (
    EosCompanionAppService,
    Gio,
    GLib
)

from .content_adjusters import (
    CONTENT_TYPE_ADJUSTERS,
    adjust_content
)
from .ekn_data import BYTE_CHUNK_SIZE


def define_content_range_from_headers_and_size(request_headers, content_size):
    '''Determine how to set the content-range headers.'''
    has_ranges, ranges = request_headers.get_ranges(content_size)

    if not has_ranges:
        return 0, content_size, content_size

    # Just use the first range
    return ranges[0].start, ranges[0].end, ranges[0].end - ranges[0].start + 1


def conditionally_wrap_blob_stream(blob, content_type, query, callback):
    '''Inspect content_type and adjust blob stream content.'''
    def _read_stream_callback(_, result):
        '''Callback once we have finished loading the stream to bytes.'''
        try:
            content_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        except GLib.Error as error:
            callback(error, None)
            return

        adjusted = adjust_content(content_type, content_bytes, query)
        memory_stream = Gio.MemoryInputStream.new_from_bytes(adjusted)
        callback(None, (memory_stream, adjusted.get_size()))


    if content_type in CONTENT_TYPE_ADJUSTERS:
        EosCompanionAppService.load_all_in_stream_to_bytes(blob.get_stream(),
                                                           chunk_size=BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=_read_stream_callback)
        return

    # We call callback here on idle so as to ensure that both invocations
    # are asynchronous (mixing asynchronous with synchronous disguised as
    # asynchronous is a bad idea)
    GLib.idle_add(lambda: callback(None,
                                   (blob.get_stream(),
                                    blob.get_content_size())))
