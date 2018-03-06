# /eoscompanion/ekn_data.py
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
'''Functions to load content from EKN shards.'''

from gi.repository import EosCompanionAppService

BYTE_CHUNK_SIZE = 256

LOAD_FROM_ENGINE_SUCCESS = 0
LOAD_FROM_ENGINE_NO_SUCH_CONTENT = 1


def load_record_blob_from_shards(shards, content_id, attr):
    '''Load a blob for an app and content_id if you already have the shards.'''
    if attr not in ('data', 'metadata'):
        raise RuntimeError('attr must be one of "data" or "metadata"')

    for shard in shards:
        record = shard.find_record_by_hex_name(content_id)

        if not record:
            continue

        return LOAD_FROM_ENGINE_SUCCESS, getattr(record, attr)

    return LOAD_FROM_ENGINE_NO_SUCH_CONTENT, None


def load_record_from_shards_async(shards,
                                  content_id,
                                  attr,
                                  callback):
    '''Load bytes from stream for app and content_id.

    :attr: must be one of 'data' or 'metadata'.

    Once loading is complete, callback will be invoked with a GAsyncResult,
    use EosCompanionAppService.finish_load_all_in_stream_to_bytes
    to get the result or handle the corresponding error.

    Returns LOAD_FROM_ENGINE_SUCCESS if a stream could be loaded,
    LOAD_FROM_ENGINE_NO_SUCH_CONTENT if the content wasn't found.
    '''
    status, blob = load_record_blob_from_shards(shards,
                                                content_id,
                                                attr)

    if status == LOAD_FROM_ENGINE_SUCCESS:
        EosCompanionAppService.load_all_in_stream_to_bytes(blob.get_stream(),
                                                           chunk_size=BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=callback)

    return status
