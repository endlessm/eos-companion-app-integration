# /eoscompanion/main.py
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
'''Main executable entry point for eos-companion-app-service.'''

from collections import namedtuple
import errno
import gi
import json
import os
import re
import sys
import urllib.parse
import uuid

gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosKnowledgeContent', '0')
gi.require_version('EosShard', '0')

from gi.repository import (
    EosCompanionAppService,
    EosKnowledgeContent as Eknc,
    Gio,
    GLib,
    GObject,
    Soup
)


def serialize_error_as_json_object(domain, code, detail={}):
    '''Serialize a GLib.Error as a JSON object.'''
    return {
        'domain': GLib.quark_to_string(domain),
        'code': code.value_nick.replace('-', '_').upper(),
        'detail': detail
    }


def json_response(msg, obj):
    '''Respond with a JSON object'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response(msg,
                                                     'application/json',
                                                     json.dumps(obj))


def html_response(msg, html):
    '''Respond with an HTML body.'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response(msg,
                                                     'text/html',
                                                     html)

def png_response(msg, image_bytes):
    '''Respond with image/png bytes.'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response_bytes(msg,
                                                           'image/png',
                                                           image_bytes)


def jpeg_response(msg, image_bytes):
    '''Respond with image/jpeg bytes.'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response_bytes(msg,
                                                           'image/jpeg',
                                                           image_bytes)


def require_query_string_param(param):
    '''Require the uri to contain certain query parameter or raise.'''
    def decorator(handler):
        def middleware(server, msg, path, query, client):
            rectified_query = query or {}
            if not rectified_query.get(param, None):
                return json_response(msg, {
                    'status': 'error',
                    'error': serialize_error_as_json_object(
                        EosCompanionAppService.error_quark(),
                        EosCompanionAppService.Error.INVALID_REQUEST,
                        detail={
                            'missing_querystring_param': param
                        }
                    )
                })

            return handler(server, msg, path, rectified_query, client)
        return middleware
    return decorator


def format_uri_with_querystring(uri, **params):
    '''Format the passed uri with the querystring params.'''
    return '{uri}?{params}'.format(uri=uri,
                                   params=urllib.parse.urlencode(params))


def companion_app_server_root_route(_, msg, *args):
    '''Not a documented route, just show the user somewhere more useful.'''
    del args

    html = '''
    <html>
        <body>
            <h1>Endless OS Companion App</h1>
            <p>This is the web-server for the Endless OS Companion App - connect
               to this computer on your Android device</p>
        </body>
    </html>
    '''
    html_response(msg, html)


@require_query_string_param('deviceUUID')
def companion_app_server_device_authenticate_route(server, msg, path, query, *args):
    '''Authorize the client.'''
    print('Authorize client: clientId={clientId}'.format(
        clientId=query['deviceUUID'])
    )
    json_response(msg, {
        'status': 'ok',
        'error': None
    })


def desktop_id_to_app_id(desktop_id):
    '''Remove .desktop suffix from desktop_id.'''
    return os.path.splitext(desktop_id)[0]


ApplicationListing = namedtuple('ApplicationListing',
                                'app_id display_name icon language')


def maybe_get_app_info_string(app_info, name):
    '''Conditionally get the locale-independent string for name.

    Return None if the operation fails due to the entry not being present
    in the app_info.
    '''
    try:
        return app_info.get_string(name)
    except GLib.Error as error:
        # XXX: See above
        return None


def application_listing_from_app_info(app_info):
    '''Convert a GDesktopAppInfo app_info to an ApplicationListing.'''
    display_name = app_info.get_display_name ()
    app_id = app_info.get_string('X-Flatpak')
    icon = app_info.get_string('Icon')

    # Fall back to using the last component of the
    # app name if that doesn't work
    language = (
        maybe_get_app_info_string(app_info,
                                  'X-Endless-Content-Language') or
        app_id.split('.')[-1]
    )

    return ApplicationListing(app_id,
                              display_name,
                              icon,
                              language)


def list_all_applications(callback):
    '''Convenience function to pass list of ApplicationListing to callback.'''
    def _callback(src, result):
        '''Callback function that gets called when we are done.'''
        infos = EosCompanionAppService.finish_list_application_infos(result)
        callback([
            application_listing_from_app_info(app_info)
            for app_info in infos
        ])

    EosCompanionAppService.list_application_infos(None, _callback)


@require_query_string_param('deviceUUID')
def companion_app_server_list_applications_route(server, msg, path, query, *args):
    '''List all applications that are available on the system.'''
    def _callback(applications):
        '''Callback function that gets called when we are done.'''
        json_response(msg, {
            'status': 'ok',
            'payload': [
                {
                    'applicationId': a.app_id,
                    'displayName': a.display_name,
                    'icon': format_uri_with_querystring(
                        '/application_icon',
                        deviceUUID=query['deviceUUID'],
                        iconName=a.icon
                    ),
                    'language': a.language
                }
                for a in applications
            ]
        })
        server.unpause_message(msg)

    print('List applications: clientId={clientId}'.format(
        clientId=query['deviceUUID'])
    )
    list_all_applications(_callback)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('iconName')
def companion_app_server_application_icon_route(server, msg, path, query, *args):
    '''Return image/png data with the application icon.'''
    def _callback(src, result):
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
                       'server_error': str(error)
                   }
               }
           })
       server.unpause_message(msg)

    print('Get application icon: clientId={clientId}, iconName={iconName}'.format(
        iconName=query['iconName'],
        clientId=query['deviceUUID']
    ))
    EosCompanionAppService.load_application_icon_data_async(query['iconName'],
                                                            cancellable=None,
                                                            callback=_callback)
    server.pause_message(msg)


# This tag is used by everything that should end up on the homepage
_GLOBAL_SET_INDICATOR_TAG = ['EknHomePageTag']


def ascertain_application_sets_from_models(models,
                                           device_uuid,
                                           application_id,
                                           done_callback):
    '''Pass application sets or an entry for the global set to callback.'''
    def _on_received_application_info(src, result):
        '''Called when we receive requested application info.'''
        try:
            listing = application_listing_from_app_info(
                EosCompanionAppService.finish_load_application_info(result)
            )
        except Exception as error:
            done_callback(error, None)
            return

        done_callback(None, [
            {
                'tags': _GLOBAL_SET_INDICATOR_TAG,
                'title': listing.display_name,
                'contentType': 'application/x-ekncontent-set',
                'thumbnail': format_uri_with_querystring(
                    '/application_icon',
                    deviceUUID=device_uuid,
                    iconName=listing.icon
                ),
                'id': '',
                'global': True
            }
        ])

    try:
        application_sets_response = [
            {
                'tags': model.get_child_tags().unpack(),
                'title': model.get_property('title'),
                'contentType': 'application/x-ekncontent-set',
                'thumbnail': format_uri_with_querystring(
                    '/content_data',
                    deviceUUID=device_uuid,
                    applicationId=application_id,
                    contentId=urllib.parse.urlparse(model.get_property('thumbnail-uri')).path[1:]
                ) if model.get_property('thumbnail-uri') else None,
                'id': urllib.parse.urlparse(model.get_property('ekn-id')).path[1:],
                'global': False
            }
            for model in models
        ]

        if application_sets_response:
            GLib.idle_add(done_callback, None, application_sets_response)
            return

        EosCompanionAppService.load_application_info(application_id,
                                                     cancellable=None,
                                                     callback=_on_received_application_info)
    except Exception as error:
        GLib.idle_add(done_callback, error, None)


# For now a limit parameter is required for queries
_SENSIBLE_QUERY_LIMIT = 500


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
def companion_app_server_list_application_sets_route(server, msg, path, query, *args):
    '''Return json listing of all sets in an application.'''
    def _on_ascertained_sets(error, sets):
        '''Callback function for when we ascertain the true sets.

        In some cases an application may not have an EknSetObject entries
        in its database. In that case, we need to create a set using
        EknHomePageTag with the same application title. Determining
        the application title is an asynchronous operation, so we need
        a callback here once it is done.'''
        if error:
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.FAILED,
                    detail={
                        'server_error': str(error)
                   }
                )
            })
        else:
            json_response(msg, {
               'status': 'ok',
               'payload': sets
            })

        server.unpause_message(msg)

    def _on_queried_sets(src, result):
       '''Callback function that gets called when we are done querying.'''
       try:
           query_results = engine.query_finish(result)
           models = query_results.get_models()

           ascertain_application_sets_from_models(models,
                                                  query['deviceUUID'],
                                                  query['applicationId'],
                                                  _on_ascertained_sets)
       except GLib.Error as error:
           json_response(msg, {
               'status': 'error',
               'error': serialize_error_as_json_object(
                   EosCompanionAppService.error_quark(),
                   EosCompanionAppService.Error.FAILED,
                   detail={
                       'server_error': str(error)
                   }
               )
           })

    print('List application sets: clientId={clientId}, applicationId={applicationId}'.format(
        applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    app_id = query['applicationId']
    engine = Eknc.Engine.get_default()

    engine.query(Eknc.QueryObject(app_id=app_id,
                                  tags_match_all=GLib.Variant('as', ['EknSetObject']),
                                  limit=_SENSIBLE_QUERY_LIMIT),
                 cancellable=None,
                 callback=_on_queried_sets)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('tags')
def companion_app_server_list_application_content_for_tags_route(server, msg, path, query, *args):
    '''Return json listing of all application content in a set.'''
    def _callback(src, result):
       '''Callback function that gets called when we are done.'''
       try:
           query_results = engine.query_finish(result)
           models = query_results.get_models()

           json_response(msg, {
               'status': 'ok',
               'payload': [
                   {
                       'displayName': model.get_property('title'),
                       'contentType': model.get_property('content-type'),
                       'thumbnail': format_uri_with_querystring(
                           '/content_data',
                           deviceUUID=query['deviceUUID'],
                           applicationId=query['applicationId'],
                           contentId=urllib.parse.urlparse(model.get_property('thumbnail-uri')).path[1:]
                       ) if model.get_property('thumbnail-uri') else None,
                       'id': urllib.parse.urlparse(model.get_property('ekn-id')).path[1:],
                       'tags': model.get_property('tags').unpack()
                   }
                   for model in models
               ]
           })
       except GLib.Error as error:
           json_response(msg, {
               'status': 'error',
               'error': serialize_error_as_json_object(
                   EosCompanionAppService.error_quark(),
                   EosCompanionAppService.Error.FAILED,
                   detail={
                       'server_error': str(error)
                   }
               )
           })
       server.unpause_message(msg)

    print('List application content for tags: clientId={clientId}, applicationId={applicationId}, tags={tags}'.format(
        tags=query['tags'], applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    app_id = query['applicationId']
    engine = Eknc.Engine.get_default()
    tags = query['tags'].split(';')

    engine.query(Eknc.QueryObject(app_id=app_id,
                                  tags_match_any=GLib.Variant('as', tags),
                                  tags_match_all=GLib.Variant('as', ['EknArticleObject']),
                                  limit=_SENSIBLE_QUERY_LIMIT),
                 cancellable=None,
                 callback=_callback)
    server.pause_message(msg)


_BYTE_CHUNK_SIZE = 256
_LOAD_FROM_ENGINE_SUCCESS = 0
_LOAD_FROM_ENGINE_NO_SUCH_APP = 1
_LOAD_FROM_ENGINE_NO_SUCH_CONTENT = 2



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
        if error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.FAILED):
            return _LOAD_FROM_ENGINE_NO_SUCH_APP, None

    shards = domain.get_shards()

    for shard in shards:
        record = shard.find_record_by_hex_name(content_id)

        if not record:
            continue

        return _LOAD_FROM_ENGINE_SUCCESS, getattr(record, attr)

    return _LOAD_FROM_ENGINE_NO_SUCH_CONTENT, None


def load_record_from_engine_async(engine, app_id, content_id, attr, callback):
    '''Load bytes from stream for app and content_id.

    :attr: must be one of 'data' or 'metadata'.

    Once loading is complete, callback will be invoked with a GAsyncResult,
    use EosCompanionAppService.finish_load_all_in_stream_to_bytes
    to get the result or handle the corresponding error.

    Returns _LOAD_FROM_ENGINE_SUCCESS if a stream could be loaded,
    _LOAD_FROM_ENGINE_NO_SUCH_APP if the app wasn't found and
    _LOAD_FROM_ENGINE_NO_SUCH_CONTENT if the content wasn't found.
    '''
    status, blob = load_record_blob_from_engine(engine,
                                                app_id,
                                                content_id,
                                                attr)

    if status == _LOAD_FROM_ENGINE_SUCCESS:
        EosCompanionAppService.load_all_in_stream_to_bytes(blob.get_stream(),
                                                           chunk_size=_BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=callback)

    return status


def rewrite_ekn_url(ekn_id, query):
    '''If the URL is an EKN url, rewrite it to be server-relative.

    This causes the applicationId and deviceUUID to be included in
    the URL query-string.
    '''
    formatted = format_uri_with_querystring(
        '/content_data',
        deviceUUID=query['deviceUUID'],
        applicationId=query['applicationId'],
        contentId=ekn_id
    )
    return formatted

def ekn_url_rewriter(query):
    '''Higher order function to rewrite a URL based on query.'''
    return lambda m: '"{}"'.format(rewrite_ekn_url(m.group('id'), query))


_RE_EKN_URL_CAPTURE = re.compile(r'"ekn\:\/\/\/(?P<id>[a-z0-9]+)"')


def _html_content_adjuster(content_bytes, query):
    '''Adjust HTML content by rewriting all the embedded URLs.

    There will be images, video and links in the document, parse it
    and rewrite it so that the links all go to somewhere that can
    be resolved by the server.

    Right now the way that this is done is a total hack (regex), in future
    we might want to depend on beautifulsoup and use that instead.
    '''
    return EosCompanionAppService.string_to_bytes(
        _RE_EKN_URL_CAPTURE.sub(ekn_url_rewriter(query),
                                EosCompanionAppService.bytes_to_string(content_bytes))
    )


CONTENT_TYPE_ADJUSTERS = {
    'text/html': _html_content_adjuster
}


def adjust_content(content_type, content_bytes, query):
    '''Adjust content if necessary.'''
    if content_type in CONTENT_TYPE_ADJUSTERS:
        return CONTENT_TYPE_ADJUSTERS[content_type](content_bytes, query)

    return content_bytes


def define_content_range_from_headers_and_size(request_headers, content_size):
    '''Determine how to set the content-range headers.'''
    has_ranges, ranges = request_headers.get_ranges(content_size)

    if not has_ranges:
        return 0, content_size, content_size

    # Just use the first range
    return ranges[0].start, ranges[0].end, ranges[0].end - ranges[0].start + 1


def conditionally_wrap_blob_stream(blob, content_type, query, callback):
    '''Inspect content_type and adjust blob stream content.'''
    def _read_stream_callback(src, result):
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
                                                           chunk_size=_BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=_read_stream_callback)
        return

    # We call callback here on idle so as to ensure that both invocations
    # are asynchronous (mixing asynchronous with synchronous disguised as
    # asynchronous is a bad idea)
    GLib.idle_add(lambda: callback(None,
                                   (blob.get_stream(),
                                    blob.get_content_size())))


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('contentId')
def companion_app_server_content_data_route(server, msg, path, query, context):
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
    def _on_got_metadata_callback(src, result):
        '''Callback function that gets called when we got the metadata.

        From here we can figure out what the content type is and load
        accordingly.
        '''
        def on_splice_finished(src, result):
            '''Callback for when we are done splicing.'''
            try:
                bytes_written = src.splice_finish(result)
            except GLib.Error as error:
                # Can't really do much here except log server side
                print(
                    'Splice operation on file failed: {error}'.format(error=error.message),
                    file=sys.stderr
                )
                return

        def on_got_offsetted_stream(src, result):
            '''Use the offsetted stream to stream the rest of the content.'''
            def on_wrote_headers(msg):
                '''Callback when headers are written.'''
                stream = context.steal_connection()
                ostream = stream.get_output_stream()
                ostream.splice_async(istream,
                                     Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
                                     GLib.PRIORITY_DEFAULT,
                                     None,
                                     on_splice_finished)

            # Now that we have the offseted stream, we can continue writing
            # the message body and insert our spliced stream in place
            istream = EosCompanionAppService.finish_fast_skip_stream(result)
            msg.connect('wrote-headers', on_wrote_headers)

            server.unpause_message(msg)

        # Now that we have the metadata, deserialize it and use the
        # contentType hint to figure out the best way to load it.
        metadata_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        content_type = json.loads(
            EosCompanionAppService.bytes_to_string(metadata_bytes)
        )['contentType']

        blob_result, blob = load_record_blob_from_engine(Eknc.Engine.get_default(),
                                                         query['applicationId'],
                                                         query['contentId'],
                                                         'data')
        if blob_result != _LOAD_FROM_ENGINE_SUCCESS:
            # No corresponding record found, EKN ID must have been invalid,
            # though it was valid for metadata...
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.INVALID_APP_ID
                    if blob_result == _LOAD_FROM_ENGINE_NO_SUCH_APP
                    else EosCompanionAppService.Error.INVALID_CONTENT_ID,
                    detail={
                        'applicationId': query['applicationId'],
                        'contentId': query['contentId']
                    }
                )
            })
            server.unpause_message(msg)
            return

        def _on_got_wrapped_stream(error, result):
            '''Take the wrapped stream, then go to an offset in it.

            Note that this is not a GAsyncReadyCallback, we instead get
            a tuple of an error or a stream and length.
            '''
            if error != None:
                print(
                    'Stream wrapping failed {error}'.format(error),
                    file=sys.stderr
                )
                json_response(msg, {
                    'status': 'error',
                    'error': serialize_error_as_json_object(
                        EosCompanionAppService.error_quark(),
                        EosCompanionAppService.Error.FAILED
                    )
                })
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
                response_headers.replace('Content-Range',
                                         'bytes {start}-{end}/{total}'.format(start=start,
                                                                              end=end,
                                                                              total=total_content_size))
                msg.set_status(Soup.Status.PARTIAL_CONTENT)
            else:
                msg.set_status(Soup.Status.OK)

            EosCompanionAppService.fast_skip_stream_async(stream,
                                                          start,
                                                          None,
                                                          on_got_offsetted_stream)

        # Need to conditionally wrap the blob in another stream
        # depending on whether it needs to be converted.
        conditionally_wrap_blob_stream(blob,
                                       content_type,
                                       query,
                                       _on_got_wrapped_stream)

    print('Get content stream: clientId={clientId}, applicationId={applicationId}, contentId={contentId}'.format(
        contentId=query['contentId'], applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    result = load_record_from_engine_async(Eknc.Engine.get_default(),
                                           query['applicationId'],
                                           query['contentId'],
                                           'metadata',
                                           _on_got_metadata_callback)

    if result == _LOAD_FROM_ENGINE_SUCCESS:
        server.pause_message(msg)
        return

    json_response(msg, {
        'status': 'error',
        'error': serialize_error_as_json_object(
            EosCompanionAppService.error_quark(),
            EosCompanionAppService.Error.INVALID_APP_ID
            if result == _LOAD_FROM_ENGINE_NO_SUCH_APP
            else EosCompanionAppService.Error.INVALID_CONTENT_ID,
            detail={
                'applicationId': query['applicationId'],
                'contentId': query['contentId']
            }
        )
    })


_RUNTIME_NAMES_FOR_APP_IDS = {}


def runtime_name_for_app_id_cached(app_id):
    '''Get the runtime name for the given Flatpak app_id.

    This does caching so as to avoid too may blocking key file reads.
    '''
    if app_id in _RUNTIME_NAMES_FOR_APP_IDS:
        return _RUNTIME_NAMES_FOR_APP_IDS[app_id]

    _RUNTIME_NAMES_FOR_APP_IDS[app_id] = EosCompanionAppService.get_runtime_name_for_app_id(app_id)
    return _RUNTIME_NAMES_FOR_APP_IDS[app_id]


def app_id_to_runtime_version(app_id):
    '''Parse the app ID using a regex and get the runtime'''
    return int(app_id.split('/')[2])


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('contentId')
def companion_app_server_content_metadata_route(server, msg, path, query, *args):
    '''Return application/json of content metadata.'''
    def _on_got_metadata_callback(src, result):
        '''Callback function that gets called when we are done.'''
        try:
            metadata_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
            metadata_json = json.loads(EosCompanionAppService.bytes_to_string(metadata_bytes))
            metadata_json['version'] = app_id_to_runtime_version(
                runtime_name_for_app_id_cached(query['applicationId'])
            )
            msg.set_status(Soup.Status.OK)
            json_response(msg, {
                'status': 'success',
                'payload': metadata_json
            })
        except GLib.Error as error:
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.FAILED,
                    detail={
                        'server_error': str(error)
                    }
                )
            })

        server.unpause_message(msg)

    print('Get content metadata: clientId={clientId}, applicationId={applicationId}, contentId={contentId}'.format(
        contentId=query['contentId'], applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    result = load_record_from_engine_async(Eknc.Engine.get_default(),
                                           query['applicationId'],
                                           query['contentId'],
                                           'metadata',
                                           _on_got_metadata_callback)

    if result == _LOAD_FROM_ENGINE_SUCCESS:
        server.pause_message(msg)
        return

    json_response(msg, {
        'status': 'error',
        'error': serialize_error_as_json_object(
            EosCompanionAppService.error_quark(),
            EosCompanionAppService.Error.INVALID_APP_ID
            if result == _LOAD_FROM_ENGINE_NO_SUCH_APP
            else EosCompanionAppService.Error.INVALID_CONTENT_ID,
            detail={
                'applicationId': query['applicationId'],
                'contentId': query['contentId']
            }
        )
    })


def all_asynchronous_function_calls_closure(calls, done_callback):
    '''Wait for each function call in calls to complete, then pass results.

    Call each single-argument function in calls, storing the resulting
    tuple of arguments in the corresponding array entry and passing the entire
    array back to done_callback.

    The single-argument to each member of calls is expected to be a callback
    function that the caller can pass to determine when the asynchronous
    operation is complete.
    '''
    def callback_thunk(index):
        '''A thunk to keep track of the index of a given call.'''
        def callback(*args):
            '''A callback for the asynchronous function, packing *args.'''
            nonlocal remaining

            results[index] = args

            remaining -= 1
            if remaining == 0:
                done_callback(results)

        return callback

    # Some state we will need to keep track of whilst the calls are ongoing
    remaining = len(calls)
    results = [None for c in calls]

    for i, call in enumerate(calls):
        call(callback_thunk(i))


def search_single_application(app_id=None,
                              set_ids=None,
                              limit=None,
                              offset=None,
                              search_term=None,
                              callback=None):
    '''Use EkncEngine.Query to run a query on a single application.

    If :set_ids: is not passed, then we search over the default subset of
    all articles and media objects. Otherwise we search over those
    sets.
    '''
    query_kwargs = {
        'app_id': app_id,
        'tags_match_any': GLib.Variant('as', set_ids or [
            'EknArticleObject',
            'EknSetObject'
        ]),
        'limit': limit or _SENSIBLE_QUERY_LIMIT,
        'offset': offset or 0
    }

    # XXX: Only add 'query' if it was actually defined. Adding it otherwise
    # triggers a warning from within eknc_query_object_get_query_parser_strings.
    #
    # Since the API is being changed in the near future, just work around
    # this for now and re-evaluate later whether or not this still occurrs
    # when using search-terms once apps are rebuilt.
    if search_term:
        query_kwargs['query'] = search_term

    query = Eknc.QueryObject(**query_kwargs)
    Eknc.Engine.get_default().query(query, None, callback)


ApplicationModel = namedtuple('ApplicationModel', 'app_id model')


def render_result_payload_for_set(app_id, model, device_uuid):
    '''Render a result payload for a set search model.'''
    return {
        'applicationId': app_id,
        'tags': model.get_child_tags().unpack(),
        'thumbnail': format_uri_with_querystring(
            '/content_data',
            deviceUUID=device_uuid,
            applicationId=app_id,
            contentId=urllib.parse.urlparse(model.get_property('thumbnail-uri')).path[1:]
        )
    }


def render_result_payload_for_content(app_id, model, device_uuid):
    '''Render a result payload for a content search model.'''
    return {
        'applicationId': app_id,
        'contentType': model.get_property('content-type'),
        'id': urllib.parse.urlparse(model.get_property('ekn-id')).path[1:],
        'tags': model.get_property('tags').unpack(),
        'thumbnail': format_uri_with_querystring(
            '/content_data',
            deviceUUID=device_uuid,
            applicationId=app_id,
            contentId=urllib.parse.urlparse(model.get_property('thumbnail-uri')).path[1:]
        )
    }


_MODEL_PAYLOAD_RENDERER_FOR_TYPE = {
    'set': render_result_payload_for_set,
    'content': render_result_payload_for_content
}

SearchModel = namedtuple('SearchModel', 'app_id display_name model model_type model_payload_renderer')


def search_models_from_application_models(application_models):
    '''Yield a SearchModel or each ApplicationModel in application_models.

    This basically just unpacks the relevant fields into SearchModel
    so that they can be accessed directly instead of being constantly
    re-unpacked.
    '''
    for app_id, model in application_models:
        display_name = model.get_property('title')
        tags = model.get_property('tags').unpack()
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
def companion_app_server_search_content_route(server, msg, path, query, *args):
    '''Return application/json of search results.

    Search the system for content matching certain predicates, returning
    a list of all content that matches those predicates, along with their
    thumbnail and associated application.

    The following parameters MAY appear at the end of the URL, and will
    limit the scope of the search:
    “applicationId”: [machine readable application ID, returned
                      by /list_applications],
    “setIds”: [machine readable set IDs, semicolon delimited,
               returned by /list_application_sets],
    “limit”: [machine readable limit integer, default 50],
    “offset”: [machine readable offset integer, default 0],
    “searchTerm”: [search term, string]
    '''
    def _on_received_results_list(truncated_models_for_applications,
                                  applications,
                                  remaining):
        '''Called when we receive all models as a part of this search.

        truncated_models_for_applications should be a list of
        ApplicationModel.

        truncated_models_for_applications is guaranteed to be truncated to
        "limit", if one was specified and offsetted by "offset", if one was
        specified, at this point.

        applications should be a list of ApplicationListing.

        remaining is the number of models which have not been served as a
        part of this query.
        '''
        json_response(msg, {
            'status': 'success',
            'payload': {
                'remaining': remaining,
                'applications': [
                    {
                        'applicationId': a.app_id,
                        'displayName': a.display_name,
                        'icon': format_uri_with_querystring(
                            '/application_icon',
                            deviceUUID=query['deviceUUID'],
                            iconName=a.icon
                        ),
                        'language': a.language
                    }
                    for a in applications
                ],
                'results': [
                    {
                        'displayName': display_name,
                        'payload': model_payload_renderer(app_id,
                                                          model,
                                                          query['deviceUUID']),
                        'type': model_type
                    }
                    for app_id, display_name, model, model_type, model_payload_renderer in
                    search_models_from_application_models(
                        truncated_models_for_applications
                    )
                ]
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
                engine, result = args_tuple

                try:
                    query_results = engine.query_finish(result)
                    all_models.extend([
                        ApplicationModel(app_id=applications[index].app_id,
                                         model=m)
                        for m in query_results.get_models()
                    ])
                except GLib.Error as error:
                    json_response(msg, {
                        'status': 'error',
                        'error': serialize_error_as_json_object(
                            EosCompanionAppService.error_quark(),
                            EosCompanionAppService.Error.FAILED,
                            detail={
                                'server_error': str(error)
                            }
                        )
                    })
                    server.unpause_message(msg)
                    return

            remaining = (
                max(0, len(all_models) - global_limit)
                if global_limit is not None else 0
            )

            # An 'end' of None here essentially means that the list will not
            # be truncated. This is the choice if global_limit is set to None
            start = global_offset if global_offset is not None else 0
            end = start + global_limit if global_limit is not None else None

            _on_received_results_list(all_models[start:end],
                                      applications,
                                      remaining)

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
                return search_single_application(app_id=application.app_id,
                                                 set_ids=set_ids,
                                                 limit=local_limit,
                                                 offset=local_offset,
                                                 search_term=search_term,
                                                 callback=callback)

            return _thunk

        all_asynchronous_function_calls_closure([
            _search_application_thunk(a) for a in applications
        ], _on_all_searches_complete_for_applications(applications,
                                                      global_limit,
                                                      global_offset))

    def _on_got_all_applications(applications):
        '''Called when we get all applications.

        When searching all applications, we do not apply a per-application
        offset, but we do apply a per-application limit since the limit is
        meant to be the upper bound.
        '''
        _search_all_applications(applications, limit, offset, limit, 0)


    def _on_got_application_info(src, result):
        '''Called when we receive info for a single application.

        Once we confirm that the application exists and we got
        info for it, we can proceed to listing content for that application
        and wrapping each item with ApplicationModel.
        '''
        try:
            info = EosCompanionAppService.finish_load_application_info(result)
        except GLib.Error as error:
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.FAILED,
                    detail={
                        'server_error': str(error)
                    }
                )
            })
            server.unpause_message(msg)
            return

        if not info:
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.INVALID_APP_ID,
                    detail={
                        'applicationId': application_id
                    }
                )
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

    set_ids = query.get('setIds', None)
    limit = query.get('limit', None)
    offset = query.get('offset', None)

    # Convert to int if defined, otherwise keep as None
    try:
        limit = int(limit) if limit else None
        offset = int(offset) if offset else None
        set_ids = set_ids.split(';') if set_ids else None
    except ValueError as error:
        # Client made an invalid request, return now
        json_response(msg, {
            'status': 'error',
            'error': serialize_error_as_json_object(
                EosCompanionAppService.error_quark(),
                EosCompanionAppService.Error.INVALID_REQUEST,
                detail={
                    'error': str(error)
                }
            )
        })
        server.unpause_message(msg)
        return

    application_id = query.get('applicationId', None)
    search_term = query.get('searchTerm', None)

    # If we got an applicationId, the assumption is that the applicationId
    # should match something so immediately list the contents of that
    # application then marshal it into an ApplicationListing format that
    # _on_received_results_list can use
    if application_id:
        EosCompanionAppService.load_application_info(application_id,
                                                     None,
                                                     _on_got_application_info)
    else:
        list_all_applications(_on_got_all_applications)
    server.pause_message(msg)


def application_hold_middleware(application, handler):
    '''Middleware function to put a hold on the application.

    This ensures that the application does not go away whilst we're handling
    HTTP traffic.
    '''
    def _handler(server, msg, *args, **kwargs):
        '''Middleware function.'''
        application.hold()
        msg.connect('finished', lambda _: application.release())
        return handler(server, msg, *args, **kwargs)

    return _handler


COMPANION_APP_ROUTES = {
    '/': companion_app_server_root_route,
    '/device_authenticate': companion_app_server_device_authenticate_route,
    '/list_applications': companion_app_server_list_applications_route,
    '/application_icon': companion_app_server_application_icon_route,
    '/list_application_sets': companion_app_server_list_application_sets_route,
    '/list_application_content_for_tags': companion_app_server_list_application_content_for_tags_route,
    '/content_data': companion_app_server_content_data_route,
    '/content_metadata': companion_app_server_content_metadata_route,
    '/search_content': companion_app_server_search_content_route
}

def create_companion_app_webserver(application):
    '''Create a HTTP server with companion app routes.'''
    server = Soup.Server()
    for path, handler in COMPANION_APP_ROUTES.items():
        server.add_handler(path, application_hold_middleware(application,
                                                             handler))

    return server


class CompanionAppService(GObject.Object):
    '''A container object for the services.'''

    def __init__(self, application, port, *args, **kwargs):
        '''Initialize the service, attach to Avahi.'''
        super().__init__(*args, **kwargs)

        # Create the server now and start listening.
        #
        # We want to listen right away as we'll probably be started by
        # socket activation
        self._server = create_companion_app_webserver(application)
        EosCompanionAppService.soup_server_listen_on_sd_fd_or_port(self._server,
                                                                   port,
                                                                   0)

    def stop(self):
        '''Close all connections and de-initialise.

        The object is useless after this point.
        '''
        self._server.disconnect()


class CompanionAppApplication(Gio.Application):
    '''Subclass of GApplication for controlling the companion app.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the application class.'''
        kwargs.update({
            'application_id': 'com.endlessm.CompanionAppService',
            'flags': Gio.ApplicationFlags.IS_SERVICE,
            'inactivity_timeout': 20000
        })
        super(CompanionAppApplication, self).__init__(*args, **kwargs)

    def do_startup(self):
        '''Just print a message.'''
        Gio.Application.do_startup(self)

        if os.environ.get('EOS_COMPANION_APP_SERVICE_PERSIST', None):
          self.hold()

        self._service = CompanionAppService(self, 1110)

    def do_dbus_register(self, connection, path):
        '''Invoked when we get a D-Bus connection.'''
        print('Got d-bus connection at {path}'.format(path=path))
        return Gio.Application.do_dbus_register(self, connection, path)

    def do_dbus_unregister(self, connection, path):
        '''Invoked when we lose a D-Bus connection.'''
        print('Lost d-bus connection at {path}'.format(path=path))
        return Gio.Application.do_dbus_unregister(self, connection, path)

    def do_activate(self):
        '''Invoked when the application is activated.'''
        print('Activated')
        return Gio.Application.do_activate(self)


def main(args=None):
    '''Entry point function.'''
    CompanionAppApplication().run(args or sys.argv)

