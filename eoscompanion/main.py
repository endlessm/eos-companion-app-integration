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


ApplicationListing = namedtuple('ApplicationListing', 'app_id display_name icon')


@require_query_string_param('deviceUUID')
def companion_app_server_list_applications_route(server, msg, path, query, *args):
    '''List all applications that are available on the system.'''
    def _callback(src, result):
        '''Callback function that gets called when we are done.'''
        infos = EosCompanionAppService.finish_list_application_infos(result)
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
                    'language': a.app_id.split('.')[-1]
                }
                for a in [
                    ApplicationListing(app_info.get_string('Desktop Entry',
                                                           'X-Flatpak'),
                                       app_info.get_string('Desktop Entry',
                                                           'Name'),
                                       app_info.get_string('Desktop Entry',
                                                           'Icon'))
                    for app_info in infos
                ]
            ]
        })
        server.unpause_message(msg)

    print('List applications: clientId={clientId}'.format(
        clientId=query['deviceUUID'])
    )
    EosCompanionAppService.list_application_infos(None, _callback)
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


def yield_models_that_have_thumbnails(models):
    '''Yield (thumbnail, EknContentObject) tuples if there is a bijection.'''
    for model in models:
        try:
            thumbnail = model.get_property('thumbnail-uri')
        except GLib.Error as error:
            continue

        if not thumbnail:
            continue

        yield (thumbnail, model)


# For now a limit parameter is required for queries
_SENSIBLE_QUERY_LIMIT = 500


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
def companion_app_server_list_application_sets_route(server, msg, path, query, *args):
    '''Return json listing of all sets in an application.'''
    def _callback(src, result):
       '''Callback function that gets called when we are done.'''
       try:
           query_results = engine.query_finish(result)
           models = query_results.get_models()

           json_response(msg, {
               'status': 'ok',
               'payload': [
                   {
                       'setId': model.get_property('title'),
                       'contentType': 'application/x-ekncontent-set',
                       'thumbnail': format_uri_with_querystring(
                           '/content_data',
                           deviceUUID=query['deviceUUID'],
                           applicationId=query['applicationId'],
                           contentId=urllib.parse.urlparse(thumbnail_uri).path[1:]
                       ),
                       'id': urllib.parse.urlparse(model.get_property('ekn-id')).path[1:]
                   }
                   for thumbnail_uri, model in
                   yield_models_that_have_thumbnails(models)
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

    print('List application sets: clientId={clientId}, applicationId={applicationId}'.format(
        applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    app_id = query['applicationId']
    engine = Eknc.Engine.get_default()

    engine.query(Eknc.QueryObject(app_id=app_id,
                                  tags_match_all=GLib.Variant('as', ['EknSetObject']),
                                  limit=_SENSIBLE_QUERY_LIMIT),
                 cancellable=None,
                 callback=_callback)
    server.pause_message(msg)


@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('setId')
def companion_app_server_list_application_content_for_set_route(server, msg, path, query, *args):
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
                           contentId=urllib.parse.urlparse(thumbnail_uri).path[1:]
                       ),
                       'id': urllib.parse.urlparse(model.get_property('ekn-id')).path[1:],
                       'tags': model.get_property('tags').unpack()
                   }
                   for thumbnail_uri, model in
                   yield_models_that_have_thumbnails(models)
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

    print('List application content for set: clientId={clientId}, applicationId={applicationId}, setId={setId}'.format(
        setId=query['setId'], applicationId=query['applicationId'], clientId=query['deviceUUID'])
    )

    app_id = query['applicationId']
    engine = Eknc.Engine.get_default()

    engine.query(Eknc.QueryObject(app_id=app_id,
                                  tags_match_all=GLib.Variant('as', [query['setId']]),
                                  limit=_SENSIBLE_QUERY_LIMIT),
                 cancellable=None,
                 callback=_callback)
    server.pause_message(msg)


_BYTE_CHUNK_SIZE = 256
_LOAD_FROM_ENGINE_SUCCESS = 0
_LOAD_FROM_ENGINE_NO_SUCH_APP = 1
_LOAD_FROM_ENGINE_NO_SUCH_CONTENT = 2


def load_record_from_engine_async(engine, app_id, content_id, attr, callback):
    '''Load bytes from stream for app and content_id.

    :attr: must be one of 'data' or 'metadata'.

    Once loading is complete, callback will be invoked with a GAsyncResult,
    use EosCompanionAppService.finish_load_all_in_stream_to_bytes
    to get the result or handle the corresponding error.

    Returns True if a stream could be loaded, False otherwise.
    '''
    if attr not in ('data', 'metadata'):
        raise RuntimeError('attr must be one of "data" or "metadata"')

    try:
        domain = engine.get_domain_for_app(app_id)
    except GLib.Error as error:
        if error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.FAILED):
            return _LOAD_FROM_ENGINE_NO_SUCH_APP

    shards = domain.get_shards()

    for shard in shards:
        record = shard.find_record_by_hex_name(content_id)

        if not record:
            continue

        stream = getattr(record, attr).get_stream()

        if not stream:
            continue

        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=_BYTE_CHUNK_SIZE,
                                                           cancellable=None,
                                                           callback=callback)
        return _LOAD_FROM_ENGINE_SUCCESS

    return _LOAD_FROM_ENGINE_NO_SUCH_CONTENT


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



@require_query_string_param('deviceUUID')
@require_query_string_param('applicationId')
@require_query_string_param('contentId')
def companion_app_server_content_data_route(server, msg, path, query, *args):
    '''Return content for contentId.

    Content-Type is content-defined. It will be determined based
    on the metadata for that content.
    '''
    def _on_got_metadata_callback(src, result):
        '''Callback function that gets called when we got the metadata.

        From here we can figure out what the content type is and load
        accordingly.
        '''
        def _on_got_data_callback(data_src, data_result):
            '''Callback function that gets called when we are done.'''
            try:
                data_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(data_result)
                msg.set_status(Soup.Status.OK)
                EosCompanionAppService.set_soup_message_response_bytes(msg,
                                                                       content_type,
                                                                       adjust_content(content_type,
                                                                                      data_bytes,
                                                                                      query))
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

        try:
            metadata_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
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

        # Now that we have the metadata, deserialize it and use the
        # contentType hint to figure out the best way to load it.
        content_type = json.loads(
            EosCompanionAppService.bytes_to_string(metadata_bytes)
        )['contentType']

        metadata_result = load_record_from_engine_async(Eknc.Engine.get_default(),
                                                        query['applicationId'],
                                                        query['contentId'],
                                                       'data',
                                                       _on_got_data_callback)
        if metadata_result != _LOAD_FROM_ENGINE_SUCCESS:
            # No corresponding record found, EKN ID must have been invalid,
            # though it was valid for metadata...
            json_response(msg, {
                'status': 'error',
                'error': serialize_error_as_json_object(
                    EosCompanionAppService.error_quark(),
                    EosCompanionAppService.Error.INVALID_APP_ID
                    if metadata_result == _LOAD_FROM_ENGINE_NO_SUCH_APP
                    else EosCompanionAppService.Error.INVALID_CONTENT_ID,
                    detail={
                        'applicationId': query['applicationId'],
                        'contentId': query['contentId']
                    }
                )
            })

    print('Get content data: clientId={clientId}, applicationId={applicationId}, contentId={contentId}'.format(
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
    '/list_application_content_for_set': companion_app_server_list_application_content_for_set_route,
    '/content_data': companion_app_server_content_data_route,
    '/content_metadata': companion_app_server_content_metadata_route
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

