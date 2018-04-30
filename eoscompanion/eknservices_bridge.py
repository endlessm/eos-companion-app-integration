# /eoscompanion/eknservices_bridge.py
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
'''Functions to query EKN databases for content.'''

import os

import re

from collections import defaultdict

from gi.repository import (
    EosCompanionAppService,
    EosShard,
    Gio,
    GLib
)

from .functional import all_asynchronous_function_calls_closure


_EKNSERVICES_DBUS_NAME_TEMPLATE = 'com.endlessm.{eknservices_name}.{search_provider_name}'
_EKNSERVICES_BASE_DBUS_PATH_TEMPLATE = '/com/endlessm/{eknservices_name}/{search_provider_name}'
_METADATA_INTERFACE = 'com.endlessm.ContentMetadata'


def encode_dbus_name(string):
    '''Encode string in dbus object path friendly characters, systemd style.'''
    return re.sub('[^A-Za-z0-9]',
                  lambda m: '_' + hex(ord(m.group(0)[0]))[2:],
                  string)


def array_to_variant(array):
    '''Encode :array: as an array of strings or an array of variants.'''
    if all([isinstance(e, str) for e in array]):
        return GLib.Variant('as', array)

    return GLib.Variant('av', [to_variant(e) for e in array if e is not None])


def dict_to_variant(dictionary):
    '''Encode :dictionary:' as a variant of type a{sv}.'''
    return GLib.Variant('a{sv}', {
        k: to_variant(v) for k, v in dictionary.items() if v is not None
    })


def to_variant(obj):
    '''Encode a python type as a variant.'''
    if isinstance(obj, dict):
        return dict_to_variant(obj)
    elif isinstance(obj, list):
        return array_to_variant(obj)
    elif isinstance(obj, int):
        return GLib.Variant('i', obj)
    elif isinstance(obj, str):
        return GLib.Variant('s', obj)

    raise RuntimeError('Don\'t know how to convert {} to a variant.'.format(
        str(obj)
    ))


def eknservices_query(conn,
                      app_id,
                      eknservices_name,
                      search_provider_name,
                      queries,
                      callback):
    '''Make a query on eknservices and send the result to callback.

    :app_id: is the id of the application to make the query on,
    :query: is a dictionary of parameters to pass to EknServices, which
            will be automatically encoded as a GVariant of type a{sv}.
    :callback: is a GAsyncReady callback.
    '''
    conn.call(
        _EKNSERVICES_DBUS_NAME_TEMPLATE.format(
            eknservices_name=eknservices_name,
            search_provider_name=search_provider_name
        ),
        os.path.join(
            _EKNSERVICES_BASE_DBUS_PATH_TEMPLATE.format(
                eknservices_name=eknservices_name,
                search_provider_name=search_provider_name
            ),
            encode_dbus_name(app_id)
        ),
        _METADATA_INTERFACE,
        'Query',
        GLib.Variant('(aa{sv})', ([{
            k: to_variant(v) for k, v in query.items() if v is not None
        } for query in queries], )),
        GLib.VariantType('(asa(a{sv}aa{sv}))'),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        callback
    )


def eknservices_shards_for_application(conn,
                                       app_id,
                                       eknservices_name,
                                       search_provider_name,
                                       callback):
    '''Ask eknservices for the application's shards and pass to callback.

    :app_id: is the id of the application to make the query on.
    :callback: is a GAsyncReady callback.
    '''
    conn.call(
        _EKNSERVICES_DBUS_NAME_TEMPLATE.format(
            eknservices_name=eknservices_name,
            search_provider_name=search_provider_name
        ),
        os.path.join(
            _EKNSERVICES_BASE_DBUS_PATH_TEMPLATE.format(
                eknservices_name=eknservices_name,
                search_provider_name=search_provider_name
            ),
            encode_dbus_name(app_id)
        ),
        _METADATA_INTERFACE,
        'Shards',
        None,
        GLib.VariantType('(as)'),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        callback
    )


def _iterate_init_shard_results(shard_init_results):
    '''Call init_finish on every result in :shard_init_results:.

    If there is an error in initializing any shard, then allow
    the exception to propagate to the caller.
    '''
    for shard, init_result in shard_init_results:
        shard.init_finish(init_result)
        yield shard


def async_init_all_shards(shard_paths, callback):
    '''Asynchronously create all shards and pass the result to callback.'''
    def _on_finished_loading_shards(shard_init_results):
        '''Callback for when shards have finished initializing.

        Check for any errors and invoke the callback accordingly,
        otherwise, invoke the callback with the resolved shards
        and metadata now.
        '''
        try:
            callback(None,
                     list(_iterate_init_shard_results(shard_init_results)))
        except GLib.Error as error:
            callback(GLib.Error(error.message,  # pylint: disable=no-member
                                EosCompanionAppService.error_quark(),
                                EosCompanionAppService.Error.FAILED),
                     None)
            return

    def _load_shard_thunk(shard_path):
        '''Asynchronously load a single shard.'''
        def _thunk(callback):
            '''Thunk that gets called.'''
            shard = EosShard.ShardFile(path=shard_path)
            shard.init_async(GLib.PRIORITY_DEFAULT,
                             None,
                             callback)

        return _thunk

    all_asynchronous_function_calls_closure([
        _load_shard_thunk(path) for path in shard_paths
    ], _on_finished_loading_shards)


# pylint: disable=line-too-long
_EKS_ERROR_TO_COMPANION_APP_ERROR = defaultdict(lambda: EosCompanionAppService.Error.FAILED, **{
    # pylint: disable=line-too-long
    'com.endlessm.EknServices.SearchProvider.AppNotFound': EosCompanionAppService.Error.INVALID_APP_ID,
    # pylint: disable=line-too-long
    'com.endlessm.EknServices.SearchProvider.UnsupportedVersion': EosCompanionAppService.Error.FAILED,
    # pylint: disable=line-too-long
    'com.endlessm.EknServices.SearchProvider.MalformedApp': EosCompanionAppService.Error.FAILED,
    # pylint: disable=line-too-long
    'com.endlessm.EknServices.SearchProvider.InvalidId': EosCompanionAppService.Error.INVALID_CONTENT_ID,
    # pylint: disable=line-too-long
    'com.endlessm.EknServices.SearchProvider.InvalidRequest': EosCompanionAppService.Error.INVALID_REQUEST
})


def _dbus_error_to_companion_app_error(error):
    '''Translate the GDBusError from EknServices to a Companion App error.'''
    code = _EKS_ERROR_TO_COMPANION_APP_ERROR[Gio.DBusError.get_remote_error(error)]
    return GLib.Error(error.message,  # pylint: disable=no-member
                      EosCompanionAppService.error_quark(),
                      code)


class EknServicesContentDbConnection(object):
    '''An EknDbConnection implemented through EknServices.'''

    def __init__(self, dbus_connection, *args, **kwargs):
        '''Initialize this object with dbus_connection.

        :dbus_connection: should be a GDBus Session Bus connection, which will
                          be re-used over the lifetime of this object.
        '''
        super().__init__(*args, **kwargs)
        self._dbus_connection = dbus_connection

    def shards_for_application(self, application_listing, callback):
        '''Load shards for application and wrap with EosShard.ShardFile.'''
        def _internal_callback(src, result):
            '''Internal GDBusConnection.call callback.'''
            try:
                response = src.call_finish(result)
            except GLib.Error as error:
                callback(_dbus_error_to_companion_app_error(error), None)
                return

            shard_paths = response.unpack()[0]
            async_init_all_shards(shard_paths, callback)

        eknservices_shards_for_application(self._dbus_connection,
                                           application_listing.app_id,
                                           application_listing.eknservices_name,
                                           application_listing.search_provider_name,
                                           _internal_callback)


    def query(self, application_listing, query, callback):
        '''Run a query and wrap the results into a python-friendly format.'''
        def _internal_callback(src, result):
            '''Internal GDBusConnection.call callback.'''
            try:
                response = src.call_finish(result)
            except GLib.Error as error:
                callback(_dbus_error_to_companion_app_error(error), None)
                return

            def _on_finished_loading_shards(error, shards):
                '''Callback for when shards have finished initializing.

                Check for any errors and invoke the callback accordingly,
                otherwise, invoke the callback with the resolved shards
                and metadata now.
                '''
                if error != None:
                    callback(error, None)
                    return

                # Take the first result, for now
                _, models = result_tuples[0]
                callback(None, [shards, models])

            shard_paths, result_tuples = response.unpack()
            async_init_all_shards(shard_paths, _on_finished_loading_shards)

        # Wrap the query in an array of length 1 to satisfy the interface
        eknservices_query(self._dbus_connection,
                          application_listing.app_id,
                          application_listing.eknservices_name,
                          application_listing.search_provider_name,
                          [query],
                          _internal_callback)
