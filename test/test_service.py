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

import re

from unittest.mock import Mock

# We need to disable wrong-import-order here as pylint insists that the
# module name 'test' is a core module (it isn't) and should be imported
# before gi, but we must import gi beforehand before any dependency in
# service_test_helpers imports things from gi without the versions
# having been set.
#
# pylint: disable=wrong-import-order
import gi

gi.require_version('ContentFeed', '0')
gi.require_version('Eknr', '0')
gi.require_version('Endless', '0')
gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosMetrics', '0')
gi.require_version('EosShard', '0')

# pylint: disable=wrong-import-order
from test.build_app import (
    force_remove_directory,
    setup_fake_apps
)
# pylint: disable=wrong-import-order
from test.service_test_helpers import (
    autoquit,
    CONTENT_APP_THUMBNAIL_EKN_ID,
    FAKE_APPS,
    FAKE_SHARD_CONTENT,
    FAKE_UUID,
    FakeContentDbConnection,
    fetch_first_content_id,
    generate_flatpak_installation_directory,
    Holdable,
    handle_headers_bytes,
    handle_json,
    json_http_request_with_uuid,
    local_endpoint,
    matches_uri_query,
    SAMPLE_ARTICLE_1_METADATA,
    SAMPLE_ARTICLE_2_METADATA,
    SAMPLE_VIDEO_1_METADATA,
    TEST_DATA_DIRECTORY,
    TestCompanionAppService,
    VIDEO_APP_THUMBNAIL_EKN_ID,
    VIDEO_APP_FAKE_CONTENT,
    with_main_loop
)

# pylint: disable=wrong-import-order
from testtools.matchers import (
    Contains,
    ContainsDict,
    Equals,
    MatchesListwise,
    MatchesSetwise,
    Not
)

# pylint: disable=wrong-import-order
from gi.repository import (
    EosCompanionAppService,
    GLib
)

# pylint: disable=wrong-import-order
from eoscompanion.service import CompanionAppService


class TestCompanionAppServiceRoutesV1(TestCompanionAppService):
    '''Test suite for the CompanionAppService class.'''

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
                                         cancellable,
                                         callback):
            '''Return an error for the content app, fine for all else.'''
            if application_listing.app_id == 'org.test.ContentApp':
                callback(GLib.Error('Malformed App',
                                    EosCompanionAppService.error_quark(),
                                    EosCompanionAppService.Error.FAILED), None)
                return

            original_query(application_listing, query, cancellable, callback)

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

    @with_main_loop
    def test_feed_endpoint(self, quit_cb):
        '''/v1/feed returns the expected content feed from the fake models.'''
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
                                                   'feed'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_feed_no_mode_invalid(self, quit_cb):
        '''/v1/feed returns INVALID_REQUEST if no mode is specified.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response, ContainsDict({
                'status': Equals('ok'),
                'payload': ContainsDict({
                    'state': ContainsDict({
                        'sources': MatchesSetwise(),
                        'index': Equals(3)
                    }),
                    'sources': MatchesSetwise(
                        ContainsDict({
                            'type': Equals('application'),
                            'detail': ContainsDict({
                                'applicationId': Equals('org.test.VideoApp'),
                                'icon': matches_uri_query('/v1/application_icon', {
                                    'iconName': MatchesSetwise(Equals('org.test.VideoApp')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'displayName': Equals('Video App'),
                                'shortDescription': Equals('A description about a Video App')
                            })
                        }),
                        ContainsDict({
                            'type': Equals('application'),
                            'detail': ContainsDict({
                                'applicationId': Equals('org.test.ContentApp'),
                                'icon': matches_uri_query('/v1/application_icon', {
                                    'iconName': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'displayName': Equals('Content App'),
                                'shortDescription': Equals('A description about a Content App')
                            })
                        })
                    ),
                    'entries': MatchesListwise([
                        ContainsDict({
                            'itemType': Equals('article'),
                            'source': ContainsDict({
                                'type': Equals('application'),
                                'detail': ContainsDict({
                                    'applicationId': Equals('org.test.ContentApp')
                                })
                            }),
                            'detail': ContainsDict({
                                'title': Equals(SAMPLE_ARTICLE_1_METADATA['title']),
                                'synopsis': Equals(SAMPLE_ARTICLE_1_METADATA['synopsis']),
                                'thumbnail': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(
                                        Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                                    ),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(Equals('sample_article_1')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'contentType': Equals('text/html')
                            })
                        }),
                        ContainsDict({
                            'itemType': Equals('artwork'),
                            'source': ContainsDict({
                                'type': Equals('application'),
                                'detail': ContainsDict({
                                    'applicationId': Equals('org.test.ContentApp')
                                })
                            }),
                            'detail': ContainsDict({
                                'author': Equals(SAMPLE_ARTICLE_2_METADATA['author']),
                                'firstDate': Equals(SAMPLE_ARTICLE_2_METADATA['firstDate']),
                                'title': Equals(SAMPLE_ARTICLE_2_METADATA['title']),
                                'thumbnail': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(
                                        Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                                    ),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(Equals('sample_article_2')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'contentType': Equals('text/html')
                            })
                        }),
                        ContainsDict({
                            'itemType': Equals('video'),
                            'source': ContainsDict({
                                'type': Equals('application'),
                                'detail': ContainsDict({
                                    'applicationId': Equals('org.test.VideoApp')
                                })
                            }),
                            'detail': ContainsDict({
                                'duration': Equals('5:04'),
                                'title': Equals(SAMPLE_VIDEO_1_METADATA['title']),
                                'thumbnail': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                                    'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v1/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                                    'contentId': MatchesSetwise(Equals('sample_video_1')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'contentType': Equals('video/webm')
                            })
                        })
                    ])
                })
            }))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'feed'),
                                    {
                                        'mode': 'ascending'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))
