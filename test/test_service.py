# /test/__init__.py
#
# Copyright (C) 2017 Endless Mobile, Inc.
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
'''Package entry point for tests.'''

import errno
import json
import logging
import os
import re
import socket

from tempfile import mkdtemp
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse
)
from unittest.mock import Mock

from test.build_app import (force_remove_directory, setup_fake_apps)

import gi

gi.require_version('Eknr', '0')
gi.require_version('Endless', '0')
gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosDiscoveryFeed', '0')
gi.require_version('EosMetrics', '0')
gi.require_version('EosShard', '0')

from gi.repository import EosCompanionAppService, Gio, GLib, Soup

from testtools import (
    TestCase
)
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    ContainsDict,
    Equals,
    MatchesAll,
    MatchesSetwise,
    Not
)

from eoscompanion.service import CompanionAppService


TOPLEVEL_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                  '..'))

# Set default loglevel to ERROR so that we don't show warnings
# on the terminal
logging.basicConfig(level=logging.ERROR)


def with_main_loop(testfunc):
    '''Decorator for tests to run with a main loop.

    Tests MUST call the 'quit_cb' parameter when they are finished, otherwise
    the test will never exit.
    '''
    # Need to disable docstrings here, otherwise the same docstring
    # will be printed for each test
    #
    # pylint: disable=missing-docstring
    def decorator(instance):
        caught_exception = None
        loop = GLib.MainLoop()

        def quit_handler(exception=None):
            '''Invoke loop.quit, propagating exception if required.'''
            nonlocal caught_exception

            if exception:
                caught_exception = exception

            loop.quit()

        def boot():
            '''Called after we enter the main loop.'''
            nonlocal caught_exception

            try:
                testfunc(instance, quit_handler)
            except Exception as exception:
                quit_handler(exception=exception)

        GLib.idle_add(boot)

        try:
            loop.run()
        except Exception as exception:
            caught_exception = exception

        if caught_exception:
            raise caught_exception

    return decorator


def quit_on_fail(callback, quit_func):
    '''Invoke callback, catching exceptions and propagating to quit_func.'''
    def handler(*args, **kwargs):
        '''Callback handler.'''
        try:
            callback(*args, **kwargs)
        except Exception as exception:
            quit_func(exception=exception)

    return handler


def autoquit(callback, quit_func):
    '''Invoke callback, catching exceptions and propagating to quit_func.

    Otherwise, unlike quit_on_fail, call quit_func without any arguments
    since it is assumed that this is the last callback that will
    need to be invoked before the test completes.
    '''
    def handler(*args, **kwargs):
        '''Callback handler.'''
        try:
            callback(*args, **kwargs)
            quit_func()
        except Exception as exception:
            quit_func(exception=exception)

    return handler


def soup_uri_with_query(uri, querystring):
    '''Create a new SoupURI for uri, with a querystring.'''
    soup_uri = Soup.URI.new(uri)
    soup_uri.set_query(querystring)

    return soup_uri


def soup_uri_with_query_object(uri, query_object):
    '''Create a new SoupURI for uri, with query string from query_object.'''
    return soup_uri_with_query(uri, urlencode(query_object))


def json_http_request_with_uuid(uuid, uri, query, callback, headers=None):
    '''Send a new HTTP request with the UUID in the header.'''
    session = Soup.Session.new()
    query.update({
        'deviceUUID': uuid
    })

    request = session.request_http_uri('GET',
                                       soup_uri_with_query_object(uri, query))
    message = request.get_message()
    message.request_headers.append('Accept', 'application/json')
    for header, value in (headers or {}).items():
        message.request_headers.append(header, value)

    EosCompanionAppService.set_soup_message_request(message,
                                                    'application/json',
                                                    '{}')
    request.send_async(None, callback)


class Holdable(object):
    '''A fake application placeholder that implements hold and release.'''

    def __init__(self):
        '''Initialize hold count.'''
        self.hold_count = 0

    def hold(self):
        '''Increment hold count.'''
        self.hold_count += 1

    def release(self):
        '''Decrement hold count.'''
        self.hold_count -= 1


def handle_text(handler):
    '''Handler middleware to parse bytestream for text.'''
    def bytes_loaded(_, result):
        '''Handle the loaded bytes.'''
        text_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
        handler(text_bytes.get_data().decode())

    def soup_bytestream_handler(obj, result):
        '''Handle the bytestream.'''
        stream = obj.send_finish(result)
        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=1024,
                                                           cancellable=None,
                                                           callback=bytes_loaded)

    return soup_bytestream_handler


def handle_json(handler):
    '''Handler middleware to parse bytestream for JSON response.'''
    def text_loaded(text):
        '''Handle the loaded text and parse JSON.'''
        handler(json.loads(text))

    return handle_text(text_loaded)


def handle_headers_bytes(handler):
    '''Handler middleware that just returns the response headers and bytes.'''
    def soup_bytestream_handler(request_obj, result):
        '''Handle the bytestream.'''
        def bytes_loaded(_, result):
            '''Handle the loaded bytes.'''
            msg_bytes = EosCompanionAppService.finish_load_all_in_stream_to_bytes(result)
            handler(msg_bytes, request_obj.get_message().response_headers)

        stream = request_obj.send_finish(result)
        EosCompanionAppService.load_all_in_stream_to_bytes(stream,
                                                           chunk_size=1024,
                                                           cancellable=None,
                                                           callback=bytes_loaded)

    return soup_bytestream_handler


class GLibEnvironmentPreservationContext(object):
    '''A class to keep track of environment variables set with GLib.setenv.

    Because we interact with a code that expects environment
    variables to be set on the C side, we need to use GLib.setenv
    as opposed to just monkey-patching os.environ, which will
    not propagate changes down to environ on the stdlib.
    '''

    def __init__(self):
        '''Initialize backup dict.'''
        super().__init__()
        self._backup = {}

    def push(self, variable, value):
        '''Push a new value for this variable into the environment.

        If the variable was already backed up then the backed up value
        is not changed, it will be restored upon a call to restore().
        '''
        if variable not in self._backup:
            self._backup[variable] = GLib.getenv(variable)

        GLib.setenv(variable, value, True)

    def restore(self):
        '''Restore or unset all backed up environment variables.'''
        for variable, value in self._backup.items():
            if value is not None:
                GLib.setenv(variable, value, True)
            else:
                GLib.unsetenv(variable)


def can_listen(port):
    '''Return True if we can listen on this port.'''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            return False
        raise error

    return True


_PORT_START = 3000
_PORT_END = 4000


def find_available_port():
    '''Scan ports to find an available one.'''
    for port in range(_PORT_START, _PORT_END):
        if can_listen(port):
            return port

    raise RuntimeError('Cannot find an available port to listen on')


def local_endpoint(port, endpoint, version='v1'):
    '''Generate localhost endpoint from port.'''
    return 'http://localhost:{port}/{version}/{endpoint}'.format(
        port=port,
        version=version,
        endpoint=endpoint
    )


TEST_DATA_DIRECTORY = os.path.join(TOPLEVEL_DIRECTORY, 'test_data')
FAKE_APPS = ['org.test.ContentApp', 'org.test.NoDisplayApp', 'org.test.VideoApp']
FAKE_UUID = 'Some UUID'

# Valid characters for EKN IDs are 0-9a-z
VIDEO_APP_THUMBNAIL_EKN_ID = 'videofilethumbnail'
CONTENT_APP_THUMBNAIL_EKN_ID = 'thumbnailforarticles'
CONTENT_APP_EMBEDDED_IMAGE_EKN_ID = 'embeddedimage'

VIDEO_APP_FAKE_CONTENT = (
    'Not actually an MPEG-4 file, just a placeholder for tests\n'
)
EMBEDDED_IMAGE_FAKE_CONTENT = (
    'Not actually an embedded image, just a placeholder\n'
)
THUMBNAIL_FAKE_CONTENT = (
    'Not actually a thumbnail JPEG file, just a placeholder\n'
)

def generate_flatpak_installation_directory():
    '''Generate a path for a flatpak installation directory.

    If BUILD_DIR is set, put it in there, for easy debugging. Otherwise,
    put it in a temporary directory.
    '''
    if 'BUILD_DIR' in os.environ:
        return os.path.join(os.environ['BUILD_DIR'], 'flatpak_installation')

    return mkdtemp(prefix='flatpak_installation')


def fetch_first_content_id(app_id, tags, port, callback, quit_cb):
    '''Request a content listing and pass first content ID to callback.'''
    def on_received_response(response):
        '''Called when we receive a response from the server.'''
        callback(response['payload'][0]['id'])

    json_http_request_with_uuid(FAKE_UUID,
                                local_endpoint(port,
                                               'list_application_content_for_tags'),
                                {
                                    'applicationId': app_id,
                                    'tags': ';'.join(tags)
                                },
                                handle_json(quit_on_fail(on_received_response,
                                                         quit_cb)))


def url_matches_path(path):
    '''Check if the candidate URL matches some path.'''
    return AfterPreprocessing(lambda u: urlparse(u).path, Equals(path))


def url_matches_query(query):
    '''Check if the candidate URL matches some query structure.'''
    return AfterPreprocessing(lambda u: parse_qs(urlparse(u).query),
                              ContainsDict(query))


def matches_uri_query(path, expected_query):
    '''Check if the passed URI with a querystring matches expected_query.

    We cannot just test for string equality here - we need to parse
    the querystring and decompose its query, then match the query
    against expected_query.
    '''
    return MatchesAll(url_matches_path(path),
                      url_matches_query(expected_query))


FAKE_SHARD_CONTENT = {
    'org.test.NoDisplayApp': {
    },
    'org.test.VideoApp': {
        'video_file': {
            'metadata': {
                'contentType': 'video/mp4',
                'duration': '5:04',
                'isServerTemplated': True,
                'license': 'CC-0',
                'originalURI': 'http://video.site/video',
                'source': 'youtube',
                'sourceName': 'YouTube',
                'synopsis': 'A synopsis about the Sample Video',
                'tags': ['EknHomePageTag', 'EknMediaObject', 'EknArticleObject'],
                'thumbnailURI': 'ekn:///'+ VIDEO_APP_THUMBNAIL_EKN_ID,
                'title': 'Sample Video'
            },
            'data': VIDEO_APP_FAKE_CONTENT.encode('utf-8')
        },
        'video_file_thumbnail': {
            'metadata': {
                'contentType': 'image/jpeg',
                '@id': 'video_file_thumbnail',
                'tags': ['EknMediaObject'],
                'title': 'Thumbnail for video'
            },
            'data': 'Not actually a thumbnail JPEG file, just a placeholder'.encode('utf-8')
        }
    },
    'org.test.ContentApp': {
        'sample_article_1': {
            'metadata': {
                'contentType': 'text/html',
                'license': 'CC-0',
                'originalURI': 'http://some.site/first',
                'source': 'wikipedia',
                'sourceName': 'Wikipedia',
                'synopsis': 'A synopsis about the Sample Article 1',
                'tags': ['First Tag', 'EknArticleObject'],
                'title': 'Sample Article 1',
                'thumbnailURI': 'ekn:///' + CONTENT_APP_THUMBNAIL_EKN_ID
            },
            'data': (
                '''
                <html>
                  <head>
                    <title>First Article</title>
                  </head>
                  <body>
                    <img src="ekn:///{}" />
                  </body>
                </html>
                '''
            ).format(CONTENT_APP_EMBEDDED_IMAGE_EKN_ID).encode('utf-8')
        },
        'sample_article_2': {
            'metadata': {
                'author': 'Some Author',
                'contentType': 'text/html',
                'firstDate': '1930-05-03T00:41:03.830398',
                'license': 'CC-0',
                'originalURI': 'http://some.site/second',
                'source': 'wikipedia',
                'sourceName': 'Wikipedia',
                'synopsis': 'A synopsis about the Sample Article 2',
                'tags': ['Second Tag', 'EknArticleObject'],
                'title': 'Sample Article 2',
                'thumbnailURI': 'ekn:///' + CONTENT_APP_THUMBNAIL_EKN_ID
            },
            'data': (
                '''
                <html>
                  <head>
                    <title>Second Article</title>
                  </head>
                  <body>
                    <p>Some content</p>
                  </body>
                </html>
                '''
            ).encode('utf-8')
        },
        'thumbnail_for_articles': {
            'metadata': {
                'contentType': 'image/jpeg',
                '@id': 'thumbnail_for_articles',
                'tags': ['EknMediaObject'],
                'title': 'Thumbnail for articles'
            },
            'data': THUMBNAIL_FAKE_CONTENT.encode('utf-8')
        },
        'embedded_image': {
            'metadata': {
                'contentType': 'image/jpeg',
                '@id': 'embedded_image',
                'tags': ['EknMediaObject'],
                'title': 'Embedded image'
            },
            'data': EMBEDDED_IMAGE_FAKE_CONTENT.encode('utf-8')
        },
        'first_set': {
            'metadata': {
                'childTags': [
                    'First Tag'
                ],
                'tags': ['First Tag', 'EknSetObject'],
                'featured': True,
                'thumbnailURI': 'ekn:///' + CONTENT_APP_THUMBNAIL_EKN_ID,
                'title': 'First Tag Set'
            },
            'data': None
        },
        'second_set': {
            'metadata': {
                'childTags': [
                    'Second Tag'
                ],
                'tags': ['Second Tag', 'EknSetObject'],
                'featured': True,
                'thumbnailURI': 'ekn:///' + CONTENT_APP_THUMBNAIL_EKN_ID,
                'title': 'Second Tag Set'
            },
            'data': None
        }
    }
}

_METADATA_KEY_TO_MODEL_KEY = {
    '@id': 'id',
    'childTags': 'child_tags',
    'contentType': 'content_type',
    'featured': 'featured',
    'isServerTemplated': 'is_server_templated',
    'license': 'license',
    'originalURI': 'original_uri',
    'source': 'source',
    'sourceName': 'source_name',
    'tags': 'tags',
    'title': 'title',
    'thumbnailURI': 'thumbnail_uri'
}

def convert_metadata_keys_to_model_keys(metadata_entry):
    '''Convert between the camel-case keys and underscore style keys.'''
    return {
        _METADATA_KEY_TO_MODEL_KEY[k]: v for k, v in metadata_entry.items()
    }


def apply_key(key, entry):
    '''Add key as the ekn_id.'''
    entry['@id'] = 'ekn:///{}'.format(key)
    return entry


class FakeEosShardBlob(object):
    '''A fake implementation of EosShardBlob.'''

    def __init__(self, blob_content):
        '''Initialize with binary blob_content.'''
        super().__init__()
        self._blob_content = blob_content

    def get_stream(self):
        '''Get a GInputStream from the data.'''
        return Gio.MemoryInputStream.new_from_data(self._blob_content)

    def get_content_size(self):
        '''Get the size in bytes of the data.'''
        return len(self._blob_content)


class FakeEosShardRecord(object):
    '''A fake implementation of EosShardRecord.'''

    def __init__(self, record_content):
        '''Initialize with record_content.'''
        super().__init__()
        self.metadata = (
            None if record_content['metadata'] is None
            else FakeEosShardBlob(json.dumps(record_content['metadata']).encode('utf-8'))
        )
        self.data = (
            None if record_content['data'] is None
            else FakeEosShardBlob(record_content['data'])
        )


class FakeEosShard(object):
    '''A fake implementation of EosShard with various bits mocked out.'''

    def __init__(self, shard_content):
        '''Initialize with shard_content.'''
        super().__init__()
        self.shard_content = shard_content

    def find_record_by_hex_name(self, hex_name):
        '''Attempt to get a record by its ID.'''
        child_content = self.shard_content.get(hex_name, None)
        if child_content is None:
            return None

        return FakeEosShardRecord(child_content)


class FakeContentDbConnection(object):
    '''An EknDbConnection with mocked out data.

    Note that we have to be careful to run any callbacks here
    asynchronously to preserve the expected invariant that callbacks
    are always executed after the route handler is first paused.
    '''

    def __init__(self, data):
        '''Initialize with data.'''
        super().__init__()
        self.data = data

    def shards_for_application(self, application_listing, callback):
        '''Create shards for the application and return them.'''
        app_id = application_listing.app_id
        app_data = self.data.get(application_listing.app_id, None)
        if app_data is None:
            GLib.idle_add(callback,
                          GLib.Error('Invalid App ID {}'.format(app_id),
                                     EosCompanionAppService.error_quark(),
                                     EosCompanionAppService.Error.INVALID_APP_ID),
                          None)
            return

        GLib.idle_add(callback, None, [FakeEosShard(app_data)])

    def query(self, application_listing, query, callback):
        '''Run a query on the fake data.

        This isn't a reimplementation of how EknQueryObject works, but it
        should be as close as possible.
        '''
        app_id = application_listing.app_id
        app_data = self.data.get(app_id, None)
        if app_data is None:
            GLib.idle_add(callback,
                          GLib.Error('Invalid App ID {}'.format(app_id),
                                     EosCompanionAppService.error_quark(),
                                     EosCompanionAppService.Error.INVALID_APP_ID),
                          None)
            return

        shards = [FakeEosShard(app_data)]
        filtered_metadata = [
            apply_key(k, entry['metadata'])
            for k, entry in app_data.items()
        ]

        search_terms = query.get('search-terms', None)
        if search_terms is not None:
            filtered_metadata = [
                entry for entry in filtered_metadata
                if entry['title'].startswith(search_terms)
            ]

        tags_match_any = query.get('tags-match-any', None)
        if tags_match_any is not None:
            filtered_metadata = [
                entry for entry in filtered_metadata
                if any([t in entry['tags'] for t in tags_match_any])
            ]

        tags_match_all = query.get('tags-match-all', None)
        if tags_match_all is not None:
            filtered_metadata = [
                entry for entry in filtered_metadata
                if all([t in entry['tags'] for t in tags_match_all])
            ]

        # Sort by title, then apply limit and offset
        filtered_metadata = sorted(filtered_metadata, key=lambda e: e['title'])

        offset = query.get('offset', None)
        if offset is not None:
            filtered_metadata = filtered_metadata[offset:]

        limit = query.get('limit', None)
        if limit is not None:
            filtered_metadata = filtered_metadata[:limit]

        models = [
            convert_metadata_keys_to_model_keys(m) for m in filtered_metadata
        ]
        GLib.idle_add(callback, None, [shards, models])


class TestCompanionAppService(TestCase):
    '''Test suite for the CompanionAppService class.'''

    # Ensure that self.listener and self.service are set to None
    # so that the references on them are dropped
    def setUp(self):
        '''Tear down the test case.'''
        super().setUp()
        self.service = None
        self._env_context = GLibEnvironmentPreservationContext()

        self._env_context.push('EOS_COMPANION_APP_FLATPAK_SYSTEM_DIR',
                               self.__class__.flatpak_installation_dir)

        # Having to explicitly enumerate all the fake flatpaks
        # like this is not ideal, but it seems like Eknc only searches
        # the hardcoded system flatpak dirs - not sure if it should
        # also check FLATPAK_SYSTEM_DIR and FLATPAK_USER_DIR
        self._env_context.push('XDG_DATA_DIRS', os.pathsep.join([
            os.path.join(self.__class__.flatpak_installation_dir,
                         'app',
                         app_id,
                         'current',
                         'active',
                         'files',
                         'share')
            for app_id in FAKE_APPS
        ] + [
            GLib.getenv('XDG_DATA_DIRS') or '',
        ]))

        self.port = find_available_port()

    def tearDown(self):
        '''Tear down the test case.'''
        self.service.stop()
        self.service = None

        self._env_context.restore()

        super().tearDown()

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        '''Set up the entire test case class.'''
        cls.flatpak_installation_dir = generate_flatpak_installation_directory()
        setup_fake_apps(FAKE_APPS,
                        TEST_DATA_DIRECTORY,
                        cls.flatpak_installation_dir)

    @classmethod
    def tearDownClass(cls):  # pylint: disable=invalid-name
        '''Tear down the entire class by deleting build testing flatpaks.'''
        force_remove_directory(cls.flatpak_installation_dir)

    @with_main_loop
    def test_make_connection_to_authenticate(self, quit_cb):
        '''Ensure that we can authenticate with the serivce.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertTrue(response['status'] == 'ok')

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_connection_reject_if_no_uuid(self, quit_cb):
        '''Reject connection if UUID is not provided.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertTrue(response['status'] == 'error')
            self.assertTrue(response['error']['code'] == 'INVALID_REQUEST')

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'device_authenticate'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_list_applications_contains_video_app(self, quit_cb):
        '''/v1/list_applications should contain video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                [a for a in response['payload'] if a['applicationId'] == 'org.test.VideoApp'][0],
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'displayName': Equals('Video App'),
                    'shortDescription': Equals('A description about a Video App'),
                    'icon': matches_uri_query('/v1/application_icon', {
                        'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    }),
                    'language': Equals('en')
                })
            )
        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_applications'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))


    @with_main_loop
    def test_list_applications_not_contains_nodisplay_app(self, quit_cb):
        '''/v1/list_applications should not contain NoDisplay app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                response['payload'],
                Not(Contains(
                    ContainsDict({
                        'applicationId': Equals('org.test.VideoApp'),
                        'displayName': Equals('Video App'),
                        'shortDescription': Equals('A description about a Video App'),
                        'icon': matches_uri_query('/v1/application_icon', {
                            'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        }),
                        'language': Equals('en')
                    })
                ))
            )
        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_applications'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_list_applications_error_no_device_uuid(self, quit_cb):
        '''/v1/list_applications should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_applications'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app(self, quit_cb):
        '''/v1/application_icon should work for video app.'''
        def on_received_response(_, headers):
            '''Called when we receive a response from the server.'''
            self.assertEqual(headers.get_content_type()[0], 'image/png')

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_headers_bytes(autoquit(on_received_response,
                                                                  quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/application_icon should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_icon_name(self, quit_cb):
        '''/v1/application_icon should return an error if iconName not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_bad_icon_name(self, quit_cb):
        '''/v1/application_icon should return an error if iconName is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_icon'),
                                    {
                                        'iconName': 'org.this.Icon.Name.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app(self, quit_cb):
        '''/v1/application_colors should work for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['colors'],
                            MatchesSetwise(Equals('#4573d9'), Equals('#98b8ff')))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/application_colors should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_application_id(self, quit_cb):
        '''/v1/application_colors should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/application_colors should return an error if applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_colors(self, quit_cb):
        '''/v1/list_application_sets should include colors.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['colors'],
                            MatchesSetwise(Equals('#4573d9'),
                                           Equals('#98b8ff')))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_home_page_tag(self, quit_cb):
        '''/v1/list_application_sets should return EknHomePageTag for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['sets'][0], ContainsDict({
                'tags': MatchesSetwise(Equals('EknHomePageTag')),
                'title': Equals('Video App'),
                'contentType': Equals('application/x-ekncontent-set'),
                'thumbnail': matches_uri_query('/v1/application_icon', {
                    'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                }),
                'id': Equals(''),
                'global': Equals(True)
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_content_app(self, quit_cb):
        '''/v1/list_application_sets should return correct tags for content app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                sorted(response['payload']['sets'], key=lambda s: s['title'])[0],
                ContainsDict({
                    'tags': MatchesSetwise(Equals('First Tag')),
                    'title': Equals('First Tag Set'),
                    'contentType': Equals('application/x-ekncontent-set'),
                    'thumbnail': matches_uri_query('/v1/content_data', {
                        'contentId': MatchesSetwise(Equals(CONTENT_APP_THUMBNAIL_EKN_ID)),
                        'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    }),
                    'global': Equals(False)
                })
            )

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.ContentApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_no_device_uuid(self, quit_cb):
        '''/list_application_sets should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_no_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationID is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_home_page_tag(self, quit_cb):
        '''/v1/list_application_content_for_tags returns video content listing.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            first = response['payload'][0]
            self.assertThat(first, ContainsDict({
                'contentType': Equals('video/mp4'),
                'displayName': Equals('Sample Video'),
                'tags': MatchesSetwise(
                    Equals('EknArticleObject'),
                    Equals('EknHomePageTag'),
                    Equals('EknMediaObject')
                ),
                'thumbnail': matches_uri_query('/v1/content_data', {
                    'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if deviceUUID not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid('',
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_application_id(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if applicationId not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_tags(self, quit_cb):
        '''/v1/list_application_content_for_tags should return an error if tags not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/list_application_sets should return an error if applicationID is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_content_for_tags'),
                                    {
                                        'applicationId': 'org.this.App.DNE',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_content_metadata_video_app(self, quit_cb):
        '''/v1/content_metadata returns some expected video content metadata.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload'], ContainsDict({
                'title': Equals('Sample Video'),
                'source': Equals('youtube'),
                'contentType': Equals('video/mp4'),
                'tags': MatchesSetwise(
                    Equals('EknArticleObject'),
                    Equals('EknHomePageTag'),
                    Equals('EknMediaObject')
                )
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/content_metadata returns an error if deviceUUID is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid('',
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_application_id(self, quit_cb):
        '''/v1/content_metadata returns an error if applicationId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_no_content_id(self, quit_cb):
        '''/v1/content_metadata returns an error if contentId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/content_metadata returns an error applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.this.App.DNE',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb),))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_metadata_video_app_error_bad_content_id(self, quit_cb):
        '''/v1/content_metadata returns an error contentId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_CONTENT_ID')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using a bad EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_metadata'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': 'nonexistent'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app(self, quit_cb):
        '''/v1/content_data returns some expected video content data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            test_string = VIDEO_APP_FAKE_CONTENT
            self.assertEqual(msg_bytes.get_data().decode('utf-8'), test_string)
            self.assertEqual(headers.get_content_length(), len(test_string))
            self.assertEqual(headers.get_content_type()[0], 'video/mp4')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_content_app(self, quit_cb):
        '''/v1/content_data returns rewritten content app data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            body = msg_bytes.get_data().decode('utf-8')

            self.assertTrue(re.match(r'^.*<img src="\/v1/content_data.*$',
                                     body,
                                     flags=re.MULTILINE | re.DOTALL) != None)

            self.assertEqual(headers.get_content_length(), len(body))
            self.assertEqual(headers.get_content_type()[0], 'text/html')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.ContentApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.ContentApp',
                               ['First Tag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_ranges(self, quit_cb):
        '''/v1/content_data returns some expected partial video content data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            # Range is inclusive, python ranges are exclusive, so add 1
            test_string = VIDEO_APP_FAKE_CONTENT
            self.assertEqual(msg_bytes.get_data().decode('utf-8'), test_string[1:11])
            self.assertEqual(headers.get_content_length(), 10)
            self.assertEqual(headers.get_content_type()[0], 'video/mp4')
            self.assertEqual(headers.get_one('Accept-Ranges'), 'bytes')
            self.assertEqual(
                headers.get_one('Content-Range'),
                'bytes 1-10/{}'.format(len(test_string))
            )

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_headers_bytes(autoquit(on_received_response,
                                                                      quit_cb)),
                                        headers={
                                            'Range': 'bytes=1-10'
                                        })

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_device_uuid(self, quit_cb):
        '''/v1/content_data returns an error if deviceUUID is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid('',
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_application_id(self, quit_cb):
        '''/v1/content_data returns an error if applicationId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_content_id(self, quit_cb):
        '''/v1/content_data returns an error if contentId is not set.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using no EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_bad_application_id(self, quit_cb):
        '''/v1/content_data returns an error applicationId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.this.App.DNE',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_bad_content_id(self, quit_cb):
        '''/v1/content_data returns an error contentId is not valid.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_CONTENT_ID')
                })
            }))

        def on_received_ekn_id(_):
            '''Make a query using bad EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data'),
                                        {
                                            'applicationId': 'org.test.VideoApp',
                                            'contentId': 'nonexistent'
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        fetch_first_content_id('org.test.VideoApp',
                               ['EknHomePageTag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_search_content_by_application_id(self, quit_cb):
        '''/v1/search_content is able to find content by applicationId.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications[0], ContainsDict({
                'applicationId': Equals('org.test.VideoApp')
            }))
            self.assertThat(results[0], ContainsDict({
                'displayName': Equals('Sample Video'),
                'payload': ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'contentType': Equals('video/mp4'),
                    'tags': MatchesSetwise(
                        Equals('EknArticleObject'),
                        Equals('EknHomePageTag'),
                        Equals('EknMediaObject')
                    ),
                    'thumbnail': matches_uri_query('/v1/content_data', {
                        'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                        'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    })
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_tags(self, quit_cb):
        '''/v1/search_content is able to find content by tags.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications[0], ContainsDict({
                'applicationId': Equals('org.test.VideoApp')
            }))
            self.assertThat(results[0], ContainsDict({
                'displayName': Equals('Sample Video'),
                'payload': ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'contentType': Equals('video/mp4'),
                    'tags': MatchesSetwise(
                        Equals('EknArticleObject'),
                        Equals('EknHomePageTag'),
                        Equals('EknMediaObject')
                    ),
                    'thumbnail': matches_uri_query('/v1/content_data', {
                        'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                        'contentId': MatchesSetwise(
                            Equals(VIDEO_APP_THUMBNAIL_EKN_ID)
                        ),
                        'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                    })
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term(self, quit_cb):
        '''/v1/search_content is able to find content by searchTerm.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                }),
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Sample Article 1'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('First Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(Equals(CONTENT_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                }),
                ContainsDict({
                    'displayName': Equals('Sample Article 2'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('Second Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(Equals(CONTENT_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                }),
                ContainsDict({
                    'displayName': Equals('Sample Video'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.VideoApp'),
                        'contentType': Equals('video/mp4'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('EknHomePageTag'),
                            Equals('EknMediaObject')
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                            'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Sampl'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term_broken_app(self, quit_cb):
        '''/v1/search_content is able to find content even if an app is broken.

        In this case the broken app should not appear in the search results,
        but the payload should still be successful.
        '''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Sample Video'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.VideoApp'),
                        'contentType': Equals('video/mp4'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('EknHomePageTag'),
                            Equals('EknMediaObject')
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                            'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                })
            ))

        def return_error_for_content_app(application_listing,
                                         query,
                                         callback):
            '''Return an error for the content app, fine for all else.'''
            if application_listing.app_id == 'org.test.ContentApp':
                callback(GLib.Error('Malformed App',
                                    EosCompanionAppService.error_quark(),
                                    EosCompanionAppService.Error.FAILED), None)
                return

            original_query(application_listing, query, callback)

        db_connection = FakeContentDbConnection(FAKE_SHARD_CONTENT)
        original_query = db_connection.query
        db_connection.query = Mock(side_effect=return_error_for_content_app)

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           db_connection)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Sampl'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term_no_nodisplay_app(self, quit_cb):
        '''/v1/search_content does not include content from NoDisplay apps.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']

            self.assertThat(applications, Not(Contains(
                ContainsDict({
                    'applicationId': Equals('org.test.NoDisplayApp')
                })
            )))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'NoDisp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_limit_and_offset(self, quit_cb):
        '''/v1/search_content is able to apply limits and offsets.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Sample Article 2'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp'),
                        'contentType': Equals('text/html'),
                        'tags': MatchesSetwise(
                            Equals('EknArticleObject'),
                            Equals('Second Tag'),
                        ),
                        'thumbnail': matches_uri_query('/v1/content_data', {
                            'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                            'contentId': MatchesSetwise(
                                Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                            ),
                            'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                        })
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Sampl',
                                        'offset': 1,
                                        'limit': 1
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_applications(self, quit_cb):
        '''/v1/search_content is able to search for applications.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            applications = response['payload']['applications']
            results = response['payload']['results']

            self.assertThat(applications, MatchesSetwise(
                ContainsDict({
                    'applicationId': Equals('org.test.ContentApp')
                })
            ))
            self.assertThat(results, MatchesSetwise(
                ContainsDict({
                    'displayName': Equals('Content App'),
                    'payload': ContainsDict({
                        'applicationId': Equals('org.test.ContentApp')
                    })
                })
            ))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'searchTerm': 'Content'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_no_filters(self, quit_cb):
        '''/v1/search_content returns an error if no filters specified.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_REQUEST')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_bad_app_id(self, quit_cb):
        '''/v1/search_content returns an error if invalid applicationId is specified.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('error'),
                'error': ContainsDict({
                    'code': Equals('INVALID_APP_ID')
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'search_content'),
                                    {
                                        'applicationId': 'org.test.This.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))
