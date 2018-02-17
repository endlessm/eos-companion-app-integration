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

from gi.repository import (
    EosCompanionAppService,
    GLib,
    Gio
)

BYTE_CHUNK_SIZE = 256

LOAD_FROM_ENGINE_SUCCESS = 0
LOAD_FROM_ENGINE_NO_SUCH_APP = 1
LOAD_FROM_ENGINE_NO_SUCH_CONTENT = 2


def load_record_blob_from_engine(engine, app_id, content_id, attr):
    '''Load a blob for app and content_id.

    :attr: must be one of 'data' or 'metadata'.

    Returns the a tuple of a (status code, blob) on success,
    (status code, None) otherwise.
    '''
    if attr not in ('data', 'metadata'):
        raise RuntimeError('attr must be one of "data" or "metadata"')

    try:
        domain = engine.get_domain_for_app(app_id)
    except GLib.Error as error:
        if (error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.FAILED) or
                error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND)):
            return LOAD_FROM_ENGINE_NO_SUCH_APP, None
        raise error

    shards = domain.get_shards()

    for shard in shards:
        record = shard.find_record_by_hex_name(content_id)

        if not record:
            continue

        return LOAD_FROM_ENGINE_SUCCESS, getattr(record, attr)

    return LOAD_FROM_ENGINE_NO_SUCH_CONTENT, None


def load_record_from_engine_async(engine, app_id, content_id, attr, callback):
    '''Load bytes from stream for app and content_id.

    :attr: must be one of 'data' or 'metadata'.

    Once loading is complete, callback will be invoked with a GAsyncResult,
    use EosCompanionAppService.finish_load_all_in_stream_to_bytes
    to get the result or handle the corresponding error.

    Returns LOAD_FROM_ENGINE_SUCCESS if a stream could be loaded,
    LOAD_FROM_ENGINE_NO_SUCH_APP if the app wasn't found and
    LOAD_FROM_ENGINE_NO_SUCH_CONTENT if the content wasn't found.
    '''
    status, blob = load_record_blob_from_engine(engine,
                                                app_id,
                                                content_id,
                                                attr)

    if status == LOAD_FROM_ENGINE_SUCCESS:
        EosCompanionAppService.load_all_in_stream_to_bytes(blob.get_stream(),
                                                           chunk_size=BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=callback)

    return status
