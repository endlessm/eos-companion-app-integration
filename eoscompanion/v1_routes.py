# /eoscompanion/v1_routes.py
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
'''V1 route definitions for eos-companion-app-service.'''

from collections import namedtuple
import itertools
import json
import logging
import os


from gi.repository import (
    Endless,
    EosCompanionAppService,
    EosMetrics,
    Gio,
    GLib,
    Soup
)

from .applications_query import (
    application_listing_from_app_info,
    list_all_applications
)
from .content_streaming import (
    conditionally_wrap_blob_stream,
    conditionally_wrap_stream,
    define_content_range_from_headers_and_size
)
from .ekn_content_adjuster import (
    EknContentAdjuster
)
from .ekn_data import (
    BYTE_CHUNK_SIZE,
    LOAD_FROM_ENGINE_NO_SUCH_CONTENT,
    load_record_blob_from_shards,
    load_record_from_shards_async
)
from .ekn_query import ascertain_application_sets_from_models
from .format import (
    format_app_icon_uri,
    format_thumbnail_uri,
    optional_format_thumbnail_uri,
    parse_uri_path_basename
)
from .functional import all_asynchronous_function_calls_closure
from .license_content_adjuster import (
    LicenseContentAdjuster
)
from .middlewares import (
    add_content_db_conn,
    apply_version_to_all_routes,
    record_metric,
    require_query_string_param
)
from .responses import (
    custom_response,
    error_response,
    json_response,
    not_found_response,
    png_response,
    respond_if_error_set
)


@require_query_string_param('deviceUUID')
@record_metric('6dad6c44-f52f-4bca-8b4c-dc203f175b97')
def companion_app_server_device_authenticate_route(server, msg, path, query, *args):
    '''Authorize the client.'''
    del server
    del path
    del args

    logging.debug('Authorize client: clientId=%s', query['deviceUUID'])
    json_response(msg, {
        'status': 'ok',
        'error': None
    })


_SUFFIX_CONTENT_TYPES = {
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.png': 'image/png',
    '.jpeg': 'image/jpeg',
    '.jpg': 'image/jpeg'
}
_CONTENT_ADJUSTERS = {
    'license': LicenseContentAdjuster
}


def _get_file_size_and_stream(file_handle, cancellable, callback):
    '''Query the file size and get a stream for it.

    This is used by the functions below to work out what the file
    size is so that it can be streamed properly.
    '''
    def _on_read_stream(_, read_result):
        '''Callback for once we have the read stream.'''
        def _on_queried_info(src, query_info_result):
            '''Callback for once we're done querying file info.'''
            try:
                file_info = src.query_info_finish(query_info_result)
            except GLib.Error as error:
                callback(error, None)
                return

            callback(None, (input_stream, file_info.get_size()))

        try:
            input_stream = file_handle.read_finish(read_result)
        except GLib.Error as error:
            callback(error, None)
            return

        input_stream.query_info_async(attributes=Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                                      io_priority=GLib.PRIORITY_DEFAULT,
                                      cancellable=cancellable,
                                      callback=_on_queried_info)

    file_handle.read_async(io_priority=GLib.PRIORITY_DEFAULT,
                           cancellable=cancellable,
                           callback=_on_read_stream)


def _stream_to_bytes(stream, cancellable, callback):
    '''Take a GInputStream and convert it to a GBytes returning result to the callback.

    This is a simple wrapper to convert load_all_in_stream_to_bytes
    into a node-style callback.
    '''
    def _callback(_, result):
        '''Called when we get the stream.'''
        try:
            content_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        except GLib.Error as error:
            callback(error, None)
            return

        callback(None, content_bytes)

    EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                       chunk_size=BYTE_CHUNK_SIZE,
                                                       cancellable=cancellable,
                                                       callback=_callback)


def _wrapped_stream_to_bytes_handler(cancellable, callback):
    '''A handler for the taking the wrapped stream and converting it to bytes.'''
    def _wrapped_stream_callback(wrapped_stream_error, wrapped_stream_result):
        '''Callback for when we receive the wrapped stream.'''
        if wrapped_stream_error is not None:
            callback(wrapped_stream_error, None)
            return

        stream, _ = wrapped_stream_result
        _stream_to_bytes(stream, cancellable, callback)

    return _wrapped_stream_callback


@require_query_string_param('deviceUUID')
@require_query_string_param('uri')
def companion_app_server_resource_route(server,
                                        msg,
                                        path,
                                        query,
                                        context,
                                        cache,
                                        version):
    '''Fetch an internal resource from a rewritten link on the page.

    This route is for fetching internal resources not tied to any particular
    application ID or content shard. For instance, we might embed a link
    to a CSS or JS file that we want to serve up to the client.

    The querystring param "uri" indicates the URI encoded path to the
    internal resource (it may be a GResource or a file).
    '''
    del context

    resource_uri = Soup.URI.decode(query['uri'])
    resource_file = Gio.File.new_for_uri(resource_uri)

    resource_suffix = os.path.splitext(resource_uri)[1]
    return_content_type = _SUFFIX_CONTENT_TYPES.get(resource_suffix, None)

    if return_content_type is None:
        error_response(
            msg,
            EosCompanionAppService.error_quark(),
            EosCompanionAppService.Error.FAILED,
            detail={
                'message': (
                    'Don\'t know content type for suffix, {}'.format(resource_suffix)
                )
            }
        )
        return

    if resource_file is None:
        not_found_response(msg, path)
        return

    content_adjuster_cls = _CONTENT_ADJUSTERS.get(query.get('adjuster', None), None)

    def _on_got_wrapped_bytes(error, content_bytes):
        '''Take the wrapped stream and send it to the client.

        For now this means reading the entire stream to bytes and
        then sending the bytes payload over. In future we should
        share logic with the /content_data route to send
        a spliced stream over.
        '''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        custom_response(msg, return_content_type, content_bytes)
        server.unpause_message(msg)

    def _on_got_stream_and_size(error, on_got_stream_result):
        '''Callback for when we get the stream and size.'''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        input_stream, file_size = on_got_stream_result
        if content_adjuster_cls is not None:
            adjuster = content_adjuster_cls.create_from_resource_query(resource_file.get_path(),
                                                                       query)
            conditionally_wrap_stream(input_stream,
                                      file_size,
                                      return_content_type,
                                      version,
                                      query,
                                      adjuster,
                                      cache,
                                      msg.cancellable,
                                      _wrapped_stream_to_bytes_handler(msg.cancellable,
                                                                       _on_got_wrapped_bytes))
            return

        _stream_to_bytes(input_stream, msg.cancellable, _on_got_wrapped_bytes)

    _get_file_size_and_stream(resource_file,
                              msg.cancellable,
                              _on_got_stream_and_size)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('name')
def companion_app_server_license_route(server,
                                       msg,
                                       path,
                                       query,
                                       context,
                                       cache,
                                       version):
    '''Fetch an internal license from a rewritten link on the page.

    This route is for for fetching license files which are embedded
    into certain documents. The licenses themselves are stored by
    eos-sdk.

    The querystring param "name" indicates the license name.
    '''
    del context

    license_name = Soup.URI.decode(query['name'])
    return_content_type = 'text/html'
    license_file = Endless.get_license_file(license_name)

    if license_file is None:
        not_found_response(msg, path)
        return

    def _on_got_wrapped_bytes(error, content_bytes):
        '''Take the wrapped stream and send it to the client.

        For now this means reading the entire stream to bytes and
        then sending the bytes payload over. In future we should
        share logic with the /content_data route to send
        a spliced stream over.
        '''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        custom_response(msg, return_content_type, content_bytes)
        server.unpause_message(msg)

    def _on_got_stream_and_size(error, on_got_stream_result):
        '''Callback for when we get the stream and size.'''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        input_stream, file_size = on_got_stream_result
        conditionally_wrap_stream(input_stream,
                                  file_size,
                                  return_content_type,
                                  version,
                                  query,
                                  LicenseContentAdjuster(license_file.get_path()),
                                  cache,
                                  msg.cancellable,
                                  _wrapped_stream_to_bytes_handler(msg.cancellable,
                                                                   _on_got_wrapped_bytes))

    _get_file_size_and_stream(license_file,
                              msg.cancellable,
                              _on_got_stream_and_size)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@record_metric('337fa66d-5163-46ae-ab20-dc605b5d7307')
def companion_app_server_list_applications_route(server,
                                                 msg,
                                                 path,
                                                 query,
                                                 context,
                                                 cache,
                                                 version):
    '''List all applications that are available on the system.'''
    del path
    del context

    def _callback(error, applications):
        '''Callback function that gets called when we are done.'''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        # Blacklist com.endlessm.encyclopedia.*
        filtered_applications = (
            application for application in applications
            if 'com.endlessm.encyclopedia.' not in application.app_id
        )

        json_response(msg, {
            'status': 'ok',
            'payload': [
                {
                    'applicationId': a.app_id,
                    'displayName': a.display_name,
                    'shortDescription': a.short_description,
                    'icon': format_app_icon_uri(version,
                                                a.icon,
                                                query['deviceUUID']),
                    'language': a.language
                }
                for a in filtered_applications
            ]
        })
        server.unpause_message(msg)

    logging.debug('List applications: clientId=%s', query['deviceUUID'])
    list_all_applications(cache, msg.cancellable, _callback)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('iconName')
def companion_app_server_application_icon_route(server, msg, path, query, *args):
    '''Return image/png data with the application icon.'''
    del path
    del args

    def _callback(_, result):
        '''Callback function that gets called when we are done.'''
        try:
            image_bytes = EosCompanionAppService.finish_load_application_icon_data_async(result)
            png_response(msg, image_bytes)
        except GLib.Error as error:
            json_response(msg, {
                'status': 'error',
                'error': {
                    'domain': GLib.quark_to_string(EosCompanionAppService.error_quark()),
                    'code': EosCompanionAppService.Error.FAILED,
                    'detail': {
                        'message': str(error)
                    }
                }
            })
        server.unpause_message(msg)

    logging.debug('Get application icon: clientId=%s, iconName=%s',
                  query['deviceUUID'],
                  query['iconName'])
    EosCompanionAppService.load_application_icon_data_async(query['iconName'],
                                                            cancellable=msg.cancellable,
                                                            callback=_callback)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
def companion_app_server_application_colors_route(server, msg, path, query, *args):
    '''Return a list of web-format primary application colors.'''
    del path
    del args

    def _callback(_, result):
        '''Callback function that gets called when we are done.'''
        try:
            color_strings = EosCompanionAppService.finish_load_application_colors(result)
            json_response(msg, {
                'status': 'ok',
                'payload': {
                    'colors': list(color_strings)
                }
            })
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId']
            })

        server.unpause_message(msg)

    logging.debug('Get application colors: clientId=%s, applicationId=%s',
                  query['deviceUUID'],
                  query['applicationId'])
    EosCompanionAppService.load_application_colors(query['applicationId'],
                                                   cancellable=msg.cancellable,
                                                   callback=_callback)
    server.pause_message(msg)


# For now a limit parameter is required for queries
_SENSIBLE_QUERY_LIMIT = 500


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@record_metric('c02a5764-7f81-48c7-aea4-1413fd4e829c')
def companion_app_server_list_application_sets_route(server,
                                                     msg,
                                                     path,
                                                     query,
                                                     context,
                                                     cache,
                                                     version,
                                                     content_db_conn):
    '''Return json listing of all sets in an application.'''
    del path
    del context

    def _on_ascertained_sets(error, sets):
        '''Callback function for when we ascertain the true sets.

        In some cases an application may not have an EknSetObject entries
        in its database. In that case, we need to create a set using
        EknHomePageTag with the same application title. Determining
        the application title is an asynchronous operation, so we need
        a callback here once it is done.

        Note that we will still want to load the application colors
        too, so we have do another asynchronous call to load them.
        '''
        def _on_loaded_application_colors(_, result):
            '''Callback function that gets called when we have the colors.'''
            try:
                color_strings = EosCompanionAppService.finish_load_application_colors(result)
                json_response(msg, {
                    'status': 'ok',
                    'payload': {
                        'colors': list(color_strings),
                        'sets': sets
                    }
                })
            except GLib.Error as load_error:
                respond_if_error_set(msg, load_error)
            server.unpause_message(msg)

        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        EosCompanionAppService.load_application_colors(query['applicationId'],
                                                       cancellable=msg.cancellable,
                                                       callback=_on_loaded_application_colors)

    def _on_queried_sets(error, result):
        '''Callback function that gets called when we are done querying.'''
        if respond_if_error_set(msg,
                                error,
                                detail={
                                    'applicationId': query['applicationId']
                                }):
            server.unpause_message(msg)
            return

        _, models = result
        ascertain_application_sets_from_models(models,
                                               version,
                                               query['deviceUUID'],
                                               query['applicationId'],
                                               cache,
                                               msg.cancellable,
                                               _on_ascertained_sets)

    def _on_got_application_info(_, result):
        '''Callback function that gets called when we get the app info.'''
        try:
            app_info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId']
            })
            server.unpause_message(msg)
            return

        application_listing = application_listing_from_app_info(app_info)
        content_db_conn.query(application_listing,
                              query={
                                  'tags-match-all': ['EknSetObject'],
                                  'limit': _SENSIBLE_QUERY_LIMIT
                              },
                              cancellable=msg.cancellable,
                              callback=_on_queried_sets)


    logging.debug('List application sets: clientId=%s, applicationId=%s',
                  query['deviceUUID'],
                  query['applicationId'])

    app_id = query['applicationId']
    EosCompanionAppService.load_application_info(app_id,
                                                 cache,
                                                 cancellable=msg.cancellable,
                                                 callback=_on_got_application_info)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('tags')
@record_metric('bef3d12c-df9b-43cd-a67c-31abc5361f03')
def companion_app_server_list_application_content_for_tags_route(server,
                                                                 msg,
                                                                 path,
                                                                 query,
                                                                 context,
                                                                 cache,
                                                                 version,
                                                                 content_db_conn):
    '''Return json listing of all application content in a set.'''
    del path
    del context

    def _callback(error, result):
        '''Callback function that gets called when we are done.'''
        if respond_if_error_set(msg,
                                error,
                                detail={
                                    'applicationId': query['applicationId']
                                }):
            server.unpause_message(msg)
            return

        _, models = result
        json_response(msg, {
            'status': 'ok',
            'payload': [
                {
                    'displayName': model['title'],
                    'contentType': model['content_type'],
                    'thumbnail': optional_format_thumbnail_uri(version,
                                                               query['applicationId'],
                                                               model,
                                                               query['deviceUUID']),
                    'id': parse_uri_path_basename(model['id']),
                    'tags': model['tags']
                }
                for model in models
            ]
        })
        server.unpause_message(msg)

    def _on_got_application_info(_, result):
        '''Callback function that gets called when we get the app info.'''
        try:
            app_info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId']
            })
            server.unpause_message(msg)
            return

        application_listing = application_listing_from_app_info(app_info)
        content_db_conn.query(application_listing,
                              query={
                                  'tags-match-all': ['EknArticleObject'],
                                  'tags-match-any': tags,
                                  'limit': _SENSIBLE_QUERY_LIMIT
                              },
                              cancellable=msg.cancellable,
                              callback=_callback)

    logging.debug(
        'List application content for tags: clientId=%s, '
        'applicationId=%s, tags=%s',
        query['deviceUUID'],
        query['applicationId'],
        query['tags'])

    app_id = query['applicationId']
    tags = query['tags'].split(';')

    EosCompanionAppService.load_application_info(app_id,
                                                 cache,
                                                 cancellable=msg.cancellable,
                                                 callback=_on_got_application_info)
    server.pause_message(msg)


def record_content_data_metric(device_uuid,
                               application_id,
                               content_title,
                               content_type,
                               referrer):
    '''Record a metric about the content being accessed.'''
    if GLib.getenv('EOS_COMPANION_APP_DISABLE_METRICS'):
        return

    payload = {
        'deviceUUID': device_uuid,
        'applicationId': application_id,
        'contentTitle': content_title,
        'contentType': content_type
    }

    if referrer:
        payload['referrerr'] = referrer

    metrics = EosMetrics.EventRecorder.get_default()
    metrics.record_event('e6541049-9462-4db5-96df-1977f3051578',
                         GLib.Variant('a{ss}', payload))


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('contentId')
def companion_app_server_content_data_route(server,
                                            msg,
                                            path,
                                            query,
                                            context,
                                            cache,
                                            version,
                                            content_db_conn):
    '''Stream content, given contentId.

    Content-Type is content-defined. It will be determined based
    on the metadata for that content.

    The client can optionally pass a Range header to start streaming
    the content from a given byte offset.

    Unfortunately, due to some of the complexities that we have to handle,
    there are a lot of callbacks that occur within this function. The general
    flow looks something like this:

    Request -> Lookup record -> Load metadata -> Load content type ->
    Lookup blob -> Conditionally wrap -> Set Content-Length
    Maybe set Content-Range -> Set Response Status ->
    Seek blob -> Send headers and wait -> Splice blob stream onto response ->
    Wait for all data to be sent -> Report on status

    Note that a lot of fighting with browsers occurred in the implementation
    of this method. If you intend to modify it, pay special attention
    to the comments since some browsers, (especially Chromium!) are very
    particular with what gets sent in the response headers and a single
    mistake will cause inexplicable loading failures part way through streams.
    '''
    del path

    def _on_got_shards_callback(shards_error, shards):
        '''Callback for when we receive the shards for an application.'''
        def _on_got_metadata_callback(load_metadata_error, metadata_bytes):
            '''Callback function that gets called when we got the metadata.

            From here we can figure out what the content type is and load
            accordingly.
            '''
            def on_splice_finished(src, result):
                '''Callback for when we are done splicing.'''
                nonlocal msg

                try:
                    src.splice_finish(result)
                except GLib.Error as splice_error:
                    # Can't really do much here except log server side
                    logging.debug(
                        'Splice operation on file failed: %s', splice_error
                    )

                # In every case, we must mark the message as finished
                # so that 'finished' signal listeners get invoked
                # (important to ensure that the application hold count
                # goes down!)
                msg.finished()

                # FIXME: This looks strange, but it is very important. It seems
                # as though accessing `msg` above creates a cyclic reference
                # since msg itself is an argument to the outer function
                # and we reference it in the inner function, but the inner
                # function is referenced by the outer function.
                #
                # Unfortunately, failure to finalize this object is a critical
                # failure for us, since the finalize handler does
                # things like closing sockets which we only have a finite
                # pool of. There is no other way to close those sockets
                # from the libsoup side. Setting this object to None
                # breaks the reference cycle and allows the object to
                # be finalized.
                msg = None
                return

            def on_got_offsetted_stream(_, result):
                '''Use the offsetted stream to stream the rest of the content.'''
                def on_wrote_headers(_):
                    '''Callback when headers are written.'''
                    stream = context.steal_connection()
                    ostream = stream.get_output_stream()
                    ostream.splice_async(istream,
                                         Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
                                         GLib.PRIORITY_DEFAULT,
                                         msg.cancellable,
                                         on_splice_finished)

                # Now that we have the offseted stream, we can continue writing
                # the message body and insert our spliced stream in place
                istream = EosCompanionAppService.finish_fast_skip_stream(result)
                msg.connect('wrote-headers', on_wrote_headers)

                server.unpause_message(msg)

            # If an error occurred, return it now
            if respond_if_error_set(msg,
                                    load_metadata_error,
                                    detail={
                                        'applicationId': query['applicationId'],
                                        'contentId': query['contentId'],
                                    }):
                server.unpause_message(msg)
                return

            # Now that we have the metadata, deserialize it and use the
            # contentType hint to figure out the best way to load it.
            content_metadata = json.loads(
                EosCompanionAppService.bytes_to_string(metadata_bytes)
            )
            content_type = content_metadata['contentType']

            blob_result, blob = load_record_blob_from_shards(shards,
                                                             query['contentId'],
                                                             'data')
            if blob_result == LOAD_FROM_ENGINE_NO_SUCH_CONTENT:
                # No corresponding record found, EKN ID must have been invalid,
                # though it was valid for metadata...
                error_response(
                    msg,
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.INVALID_CONTENT_ID,
                    detail={
                        'applicationId': query['applicationId'],
                        'contentId': query['contentId']
                    }
                )
                server.unpause_message(msg)
                return

            def _on_got_wrapped_stream(error, result):
                '''Take the wrapped stream, then go to an offset in it.

                Note that this is not a GAsyncReadyCallback, we instead get
                a tuple of an error or a stream and length.
                '''
                if respond_if_error_set(msg, error):
                    logging.warning(
                        'Stream wrapping failed %s', error
                    )
                    server.unpause_message(msg)
                    return

                stream, total_content_size = result

                # Now that we have the stream, we can post back with how big the
                # content is
                response_headers = msg.get_property('response-headers')
                request_headers = msg.get_property('request-headers')

                start, end, length = define_content_range_from_headers_and_size(request_headers,
                                                                                total_content_size)

                # Note that the length we set here is the number of bytes that will
                # be contained in the payload, but this is different from the
                # 'total' that is sent in the Content-Range header
                #
                # Essentially, it is end - start + 1, taking into account the
                # requirements for the end marker below.
                response_headers.set_content_length(length)
                response_headers.set_content_type(content_type)
                response_headers.replace('Connection', 'keep-alive')

                # Add the article thumbnail uri to the header
                # we only want to add the image when it is content
                # from a Wikipedia or Wikihow source
                thumbnail_uri = content_metadata.get('thumbnail', None)
                is_wiki_source = content_metadata.get('source', None) in ('wikipedia', 'wikihow')
                if thumbnail_uri is not None and is_wiki_source:
                    formatted_thumbnail_uri = format_thumbnail_uri(version,
                                                                   query['applicationId'],
                                                                   thumbnail_uri,
                                                                   query['deviceUUID'])
                    response_headers.replace('X-Endless-Article-Thumbnail', formatted_thumbnail_uri)

                # If we did not get a Range header, then we do not want to set
                # Content-Range, nor do we want to respond with PARTIAL_CONTENT as
                # the status code. If we do that, browsers like Firefox will
                # handle it fine, but Chrome and VLC just choke. Note that we
                # not even want to send Accept-Ranges unless the
                # requested a Range.
                if request_headers.get_one('Range'):
                    response_headers.replace('Accept-Ranges', 'bytes')

                    # The format of this must be
                    #
                    #   'bytes start-end/total'
                    #
                    # The 'end' marker must be one byte less than 'total' and
                    # all bytes up to 'end' must be sent by the implementation.
                    # Browsers like Chrome will, upon seeking, attempt to load
                    # last 6524 bytes of the stream and won't continue until all of
                    # those bytes have been sent by the client (at which point
                    # it actually loads from the correct place).
                    response_headers.replace(
                        'Content-Range',
                        'bytes {start}-{end}/{total}'.format(start=start,
                                                             end=end,
                                                             total=total_content_size)
                    )
                    msg.set_status(Soup.Status.PARTIAL_CONTENT)
                else:
                    msg.set_status(Soup.Status.OK)

                EosCompanionAppService.fast_skip_stream_async(stream,
                                                              start,
                                                              msg.cancellable,
                                                              on_got_offsetted_stream)

            # Report a metric now
            record_content_data_metric(query['deviceUUID'],
                                       query['applicationId'],
                                       query.get('title', 'Untitled'),
                                       content_type,
                                       query.get('referrer', None))

            # Need to conditionally wrap the blob in another stream
            # depending on whether it needs to be converted.
            conditionally_wrap_blob_stream(blob,
                                           content_type,
                                           version,
                                           query,
                                           EknContentAdjuster(content_metadata,
                                                              content_db_conn,
                                                              shards),
                                           cache,
                                           msg.cancellable,
                                           _on_got_wrapped_stream)

        if respond_if_error_set(msg,
                                shards_error,
                                detail={
                                    'applicationId': query['applicationId'],
                                    'contentId': query['contentId'],
                                }):
            server.unpause_message(msg)
            return

        load_record_from_shards_async(shards,
                                      query['contentId'],
                                      'metadata',
                                      _on_got_metadata_callback)

    def _on_got_application_info(_, result):
        '''Callback function that gets called when we get the app info.'''
        try:
            app_info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId'],
                'message': str(error)
            })
            server.unpause_message(msg)
            return

        application_listing = application_listing_from_app_info(app_info)
        content_db_conn.shards_for_application(application_listing,
                                               cancellable=msg.cancellable,
                                               callback=_on_got_shards_callback)

    logging.debug(
        'Get content stream: clientId=%s, '
        'applicationId=%s, contentId=%s',
        query['deviceUUID'],
        query['applicationId'],
        query['contentId']
    )
    EosCompanionAppService.load_application_info(query['applicationId'],
                                                 cache,
                                                 cancellable=msg.cancellable,
                                                 callback=_on_got_application_info)
    server.pause_message(msg)


def app_id_to_runtime_version(app_id):
    '''Parse the app ID using a regex and get the runtime'''
    return int(app_id.split('/')[2])


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('contentId')
@record_metric('3a4eff55-5d01-48c8-a827-fca5732fd767')
def companion_app_server_content_metadata_route(server,
                                                msg,
                                                path,
                                                query,
                                                context,
                                                cache,
                                                version,
                                                content_db_conn):
    '''Return application/json of content metadata.'''
    del path
    del context
    del version

    def _on_got_shards_callback(shards_error, shards):
        '''Callback function that gets called when we get our shards.'''
        def _on_got_metadata_callback(load_metadata_error, metadata_bytes):
            '''Callback function that gets called when we are done.'''
            if respond_if_error_set(msg,
                                    load_metadata_error,
                                    detail={
                                        'applicationId': query['applicationId'],
                                    },
                                    error_mappings={
                                        # pylint: disable=line-too-long
                                        (Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND): EosCompanionAppService.Error.INVALID_APP_ID
                                    }):
                server.unpause_message(msg)
                return

            metadata_json = json.loads(EosCompanionAppService.bytes_to_string(metadata_bytes))
            metadata_json['version'] = app_id_to_runtime_version(
                EosCompanionAppService.get_runtime_spec_for_app_id(
                    query['applicationId'],
                    cache
                )
            )
            msg.set_status(Soup.Status.OK)
            json_response(msg, {
                'status': 'ok',
                'payload': metadata_json
            })
            server.unpause_message(msg)

        if respond_if_error_set(msg,
                                shards_error,
                                detail={
                                    'applicationId': query['applicationId'],
                                    'contentId': query['contentId']
                                }):
            server.unpause_message(msg)
            return

        load_record_from_shards_async(shards,
                                      query['contentId'],
                                      'metadata',
                                      _on_got_metadata_callback)


    def _on_got_application_info(_, result):
        '''Callback function that gets called when we get the app info.'''
        try:
            app_info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId']
            })
            server.unpause_message(msg)
            return

        application_listing = application_listing_from_app_info(app_info)
        content_db_conn.shards_for_application(application_listing,
                                               cancellable=msg.cancellable,
                                               callback=_on_got_shards_callback)

    logging.debug(
        'Get content metadata: clientId=%s, '
        'applicationId=%s, contentId=%s',
        query['deviceUUID'],
        query['applicationId'],
        query['contentId']
    )
    EosCompanionAppService.load_application_info(query['applicationId'],
                                                 cache,
                                                 cancellable=msg.cancellable,
                                                 callback=_on_got_application_info)
    server.pause_message(msg)


def search_single_application(content_db_conn,
                              application_listing=None,
                              tags=None,
                              limit=None,
                              offset=None,
                              search_term=None,
                              cancellable=None,
                              callback=None):
    '''Use :content_db_conn: to run a query on a single application.

    If :tags: is not passed, then we search over the default subset of
    all articles and media objects. Otherwise we search over those
    sets.
    '''
    content_db_conn.query(application_listing,
                          query={
                              'tags-match-any': tags or [
                                  'EknArticleObject',
                                  'EknSetObject'
                              ],
                              'limit': limit or _SENSIBLE_QUERY_LIMIT,
                              'offset': offset or 0,
                              'search-terms': search_term
                          },
                          cancellable=cancellable,
                          callback=callback)


ApplicationModel = namedtuple('ApplicationModel', 'app_id model')


def render_result_payload_for_set(version, app_id, model, device_uuid):
    '''Render a result payload for a set search model.'''
    return {
        'applicationId': app_id,
        'tags': model['child_tags'],
        'thumbnail': optional_format_thumbnail_uri(version,
                                                   app_id,
                                                   model,
                                                   device_uuid)
    }


def render_result_payload_for_content(version, app_id, model, device_uuid):
    '''Render a result payload for a content search model.'''
    return {
        'applicationId': app_id,
        'contentType': model['content_type'],
        'id': parse_uri_path_basename(model['id']),
        'tags': model['tags'],
        'thumbnail': optional_format_thumbnail_uri(version,
                                                   app_id,
                                                   model,
                                                   device_uuid)
    }


_MODEL_PAYLOAD_RENDERER_FOR_TYPE = {
    'set': render_result_payload_for_set,
    'content': render_result_payload_for_content
}

SearchModel = namedtuple('SearchModel',
                         'app_id display_name model model_type model_payload_renderer')


def search_models_from_application_models(application_models):
    '''Yield a SearchModel or each ApplicationModel in application_models.

    This basically just unpacks the relevant fields into SearchModel
    so that they can be accessed directly instead of being constantly
    re-unpacked.
    '''
    for app_id, model in application_models:
        display_name = model['title']
        tags = model['tags']
        model_type = (
            'set' if 'EknSetObject' in tags else 'content'
        )
        model_payload_renderer = _MODEL_PAYLOAD_RENDERER_FOR_TYPE[model_type]

        yield SearchModel(app_id=app_id,
                          display_name=display_name,
                          model=model,
                          model_type=model_type,
                          model_payload_renderer=model_payload_renderer)


@require_query_string_param('deviceUUID')
@record_metric('9f06d0f7-677e-43ca-b732-ccbb40847a31')
def companion_app_server_search_content_route(server,
                                              msg,
                                              path,
                                              query,
                                              context,
                                              cache,
                                              version,
                                              content_db_conn):
    '''Return application/json of search results.

    Search the system for content matching certain predicates, returning
    a list of all content that matches those predicates, along with their
    thumbnail and associated application.

    The following parameters MAY appear at the end of the URL, and will
    limit the scope of the search:
    “applicationId”: [machine readable application ID, returned
                      by /list_applications],
    “tags”: [machine readable set IDs, semicolon delimited,
             returned by /list_application_sets],
    “limit”: [machine readable limit integer, default 50],
    “offset”: [machine readable offset integer, default 0],
    “searchTerm”: [search term, string]
    '''
    del path
    del context

    def _on_received_results_list(models,
                                  matched_application_ids,
                                  applications,
                                  global_limit,
                                  global_offset):
        '''Called when we receive all models as a part of this search.

        truncated_models_for_applications should be a list of
        ApplicationModel.

        truncated_models_for_applications is guaranteed to be truncated to
        "limit", if one was specified and offsetted by "offset", if one was
        specified, at this point.

        matched_application_ids is a list of application IDs
        for which the application name actually matched the search term.

        applications should be a list of ApplicationListing, which is
        all applications that should be included in the "applications"
        section of the response.

        remaining is the number of models which have not been served as a
        part of this query.
        '''
        # An 'end' of None here essentially means that the list will not
        # be truncated. This is the choice if global_limit is set to None
        start = global_offset if global_offset is not None else 0
        end = start + global_limit if global_limit is not None else None

        # We need to construct an in-memory hashtable of application
        # IDs to names to at least get nlogn lookup
        applications_hashtable = {
            a.app_id: a.display_name for a in applications
        }

        # all_results is the application names that matched the search term,
        # plus all the models that matched the search term
        all_results = sorted(list(itertools.chain.from_iterable([
            [
                {
                    'displayName': applications_hashtable[app_id],
                    'payload': {
                        'applicationId': app_id
                    },
                    'type': 'application'
                }
                for app_id in matched_application_ids
            ],
            [
                {
                    'displayName': display_name,
                    'payload': model_payload_renderer(version,
                                                      app_id,
                                                      model,
                                                      query['deviceUUID']),
                    'type': model_type
                }
                for app_id, display_name, model, model_type, model_payload_renderer in
                search_models_from_application_models(
                    models
                )
            ]
        ])), key=lambda r: r['displayName'])

        # Determine which applications were seen in the truncated model
        # set or if their name matched the search query and then include
        # them in the results list
        truncated_results = all_results[start:end]

        seen_application_ids = set(itertools.chain.from_iterable([[
            r['payload']['applicationId']
            for r in truncated_results
            if r['type'] != 'application'
        ], [app_id for app_id in matched_application_ids]]))
        relevant_applications = [
            a for a in applications if a.app_id in seen_application_ids
        ]

        remaining = (
            max(0, len(all_results) - global_limit)
            if global_limit is not None else 0
        )

        json_response(msg, {
            'status': 'ok',
            'payload': {
                'remaining': remaining,
                'applications': [
                    {
                        'applicationId': a.app_id,
                        'displayName': a.display_name,
                        'shortDescription': a.short_description,
                        'icon': format_app_icon_uri(version,
                                                    a.icon,
                                                    query['deviceUUID']),
                        'language': a.language
                    }
                    for a in relevant_applications
                ],
                'results': truncated_results
            }
        })
        server.unpause_message(msg)

    def _on_all_searches_complete_for_applications(applications,
                                                   global_limit,
                                                   global_offset):
        '''A thunk to preserve the list of applications.

        Note that each result is guaranteed to come back in the same order
        that requests were added to all_asynchronous_function_calls_closure,
        so if applications is in the same order, we can look up the
        corresponding application in applications for each index.
        '''
        def _on_all_searches_complete(search_results):
            '''Called when we receive the result of all searches.

            Examine the result of every search call for errors and if so,
            immediately return the error to the client. Otherwise, take all
            the models and marshal them into a single list, truncated by the
            search limit and pass to _on_received_results_list.
            '''
            all_models = []

            for index, args_tuple in enumerate(search_results):
                error, result = args_tuple

                if error is not None:
                    # FAILED is a non-fatal error, since it indicates
                    # something wrong with the app or content itself. We just
                    # log on those errors and continue the search. Other
                    # errors are due to invalid arguments from the caller
                    # which should be reported back.
                    if not error.matches(EosCompanionAppService.error_quark(),
                                         EosCompanionAppService.Error.FAILED):
                        respond_if_error_set(msg, error)
                        server.unpause_message(msg)
                        return
                    else:
                        logging.warning(
                            "Encountered error searching application %s: %s",
                            applications[index].app_id,
                            error.message
                        )
                        continue

                _, models = result
                all_models.extend([
                    ApplicationModel(app_id=applications[index].app_id,
                                     model=m)
                    for m in models
                ])


            # Search for applications. The g_desktop_app_info_search function
            # will search all applications using an in-memory index
            # according to its own internal criteria. The returned
            # arrays will be arrays of applications which each have
            # identical scores. Since we don't actually know what the scores
            # are, just chain all the arrays together and fold them into
            # a set. Finally, we only care about content applications, so
            # take the intersection between the returned results
            matched_application_ids = set([
                desktop_id[:desktop_id.rfind('.desktop')] for desktop_id in
                itertools.chain.from_iterable(Gio.DesktopAppInfo.search(search_term))
            ]) if search_term else set([])
            matched_application_ids &= set(
                a.app_id for a in applications
            )

            _on_received_results_list(all_models,
                                      matched_application_ids,
                                      applications,
                                      global_limit,
                                      global_offset)

        return _on_all_searches_complete

    def _search_all_applications(applications,
                                 global_limit,
                                 global_offset,
                                 local_limit,
                                 local_offset):
        '''Search all applications with the given limit and offset.

        Search each application for our search term. This is done through
        all_asynchronous_function_calls_closure which calls a list of
        zero-argument asynchronous functions and marshals their results into a
        list of tuples of (error, result), depending on whether an error
        occurred. The _on_received_all_results callback is then called with
        the overall list, where results are refined down into a list of
        models, and then filtered accordingly.

        :global_limit: refers to the limit on all results from all
        applications.
        :global_offset: is the offset into the the result set returned by
        all applications.

        :local_limit: refers to the per-application content limit.
        :local_offset: refers to the offset within each application.
        '''
        def _search_application_thunk(application):
            '''Partially applied function to search a single application.

            We have to use this instead of a lambda, since lambda closure
            semantics are such that a reference to the loop variable, rather
            than the loop variable's value, will be captured.
            '''
            def _thunk(callback):
                '''Thunk that gets called.'''
                return search_single_application(content_db_conn,
                                                 application_listing=application,
                                                 tags=tags,
                                                 limit=local_limit,
                                                 offset=local_offset,
                                                 search_term=search_term,
                                                 cancellable=msg.cancellable,
                                                 callback=callback)

            return _thunk

        all_asynchronous_function_calls_closure([
            _search_application_thunk(a) for a in applications
        ], _on_all_searches_complete_for_applications(applications,
                                                      global_limit,
                                                      global_offset))

    def _on_got_all_applications(error, applications):
        '''Called when we get all applications.

        When searching all applications, we do not apply a per-application
        offset, but we do apply a per-application limit since the limit is
        meant to be the upper bound.

        Note that the per-application limit actually needs to
        be the upper bound of the slice that we take from all query
        results, since the offset is applied to the reconciled
        set and not each individual source. For instance, if we
        have a limit of 1 and an offset of 1, then we need at least
        two results from a single source in order to apply that
        global limit and offset correctly, otherwise the slice would
        run off the end of the result set when we could have had more.
        '''
        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        _search_all_applications(applications,
                                 limit,
                                 offset,
                                 (limit or 0) + (offset or 0),
                                 0)


    def _on_got_application_info(_, result):
        '''Called when we receive info for a single application.

        Once we confirm that the application exists and we got
        info for it, we can proceed to listing content for that application
        and wrapping each item with ApplicationModel.
        '''
        try:
            info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            respond_if_error_set(msg, error, detail={
                'applicationId': query['applicationId']
            })
            server.unpause_message(msg)
            return

        # Now that we have our application info, we can do a search on this
        # application (just do a search over all elements of our scalar-valued
        # list of applications). Note here that we pass a local limit and
        # offset, but not a global limit and offset. We are only searching
        # a single application so we can allow Xapian to do the hard work for
        # us.
        _search_all_applications([application_listing_from_app_info(info)],
                                 None,
                                 None,
                                 limit,
                                 offset)

    tags = query.get('tags', None)
    limit = query.get('limit', None)
    offset = query.get('offset', None)

    # Convert to int if defined, otherwise keep as None
    try:
        limit = int(limit) if limit else None
        offset = int(offset) if offset else None
        tags = tags.split(';') if tags else None
    except ValueError as error:
        # Client made an invalid request, return now
        error_response(
            msg,
            EosCompanionAppService.error_quark(),
            EosCompanionAppService.Error.INVALID_REQUEST,
            detail={
                'message': str(error)
            }
        )
        return

    application_id = query.get('applicationId', None)
    search_term = query.get('searchTerm', None)

    if not any([application_id, search_term, tags]):
        error_response(
            msg,
            EosCompanionAppService.error_quark(),
            EosCompanionAppService.Error.INVALID_REQUEST,
            detail={
                'message': 'One of "applicationId", "searchTerm", or "tags" must be specified'
            }
        )
        return

    # If we got an applicationId, the assumption is that the applicationId
    # should match something so immediately list the contents of that
    # application then marshal it into an ApplicationListing format that
    # _on_received_results_list can use
    if application_id:
        EosCompanionAppService.load_application_info(application_id,
                                                     cache,
                                                     msg.cancellable,
                                                     _on_got_application_info)
    else:
        list_all_applications(cache, msg.cancellable, _on_got_all_applications)
    server.pause_message(msg)


def create_companion_app_routes_v1(content_db_conn):
    '''Create fully-applied routes from the passed content_db_conn.

    :content_db_conn: will be bound as the final argument to routes
                      that require it. This allows for a different
                      query mechanism to be injected during test
                      scenarios, where we don't want a dependency
                      on the database, which may require network
                      activity.
    '''
    return apply_version_to_all_routes({
        '/device_authenticate': companion_app_server_device_authenticate_route,
        '/list_applications': companion_app_server_list_applications_route,
        '/application_icon': companion_app_server_application_icon_route,
        '/application_colors': companion_app_server_application_colors_route,
        '/list_application_sets': add_content_db_conn(
            companion_app_server_list_application_sets_route,
            content_db_conn
        ),
        '/list_application_content_for_tags': add_content_db_conn(
            companion_app_server_list_application_content_for_tags_route,
            content_db_conn
        ),
        '/content_data': add_content_db_conn(
            companion_app_server_content_data_route,
            content_db_conn
        ),
        '/content_metadata': add_content_db_conn(
            companion_app_server_content_metadata_route,
            content_db_conn
        ),
        '/search_content': add_content_db_conn(
            companion_app_server_search_content_route,
            content_db_conn
        ),
        '/resource': companion_app_server_resource_route,
        '/license': companion_app_server_license_route
    }, 'v1')
