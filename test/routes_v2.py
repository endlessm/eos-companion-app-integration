# /test/routes_v2.py
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
#
# pylint: disable=no-member,attribute-defined-outside-init
'''Tests for the /v2 routes.'''


import re

from unittest.mock import Mock

from test.service_test_helpers import (
    autoquit,
    CONTENT_APP_THUMBNAIL_EKN_ID,
    FAKE_SHARD_CONTENT,
    FAKE_UUID,
    FakeContentDbConnection,
    fetch_first_content_id,
    Holdable,
    handle_headers_bytes,
    handle_json,
    json_http_request_with_uuid,
    local_endpoint,
    matches_uri_query,
    modify_app_runtime,
    quit_on_fail,
    SAMPLE_ARTICLE_1_METADATA,
    SAMPLE_ARTICLE_2_METADATA,
    SAMPLE_VIDEO_1_METADATA,
    VIDEO_APP_THUMBNAIL_EKN_ID,
    VIDEO_APP_FAKE_CONTENT,
    with_main_loop
)

from testtools.matchers import (
    Contains,
    ContainsDict,
    Equals,
    MatchesSetwise,
    MatchesListwise,
    Not
)

import gi

gi.require_version('ContentFeed', '0')
gi.require_version('Eknr', '0')
gi.require_version('Endless', '0')
gi.require_version('EosCompanionAppService', '1.0')
gi.require_version('EosMetrics', '0')
gi.require_version('EosShard', '0')

from gi.repository import (
    EosCompanionAppService,
    GLib
)

from eoscompanion.service import CompanionAppService


class CompanionAppServiceRoutesV2(object):
    '''Test suite for the CompanionAppService class, v2 routes.'''

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
                                                   'device_authenticate',
                                                   version='v2'),
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
                                                   'device_authenticate',
                                                   version='v2'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_list_applications_contains_video_app(self, quit_cb):
        '''/v2/list_applications should contain video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                [a for a in response['payload'] if a['applicationId'] == 'org.test.VideoApp'][0],
                ContainsDict({
                    'applicationId': Equals('org.test.VideoApp'),
                    'displayName': Equals('Video App'),
                    'shortDescription': Equals('A description about a Video App'),
                    'icon': matches_uri_query('/v2/application_icon', {
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
                                                   'list_applications',
                                                   version='v2'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))


    @with_main_loop
    def test_list_applications_not_contains_nodisplay_app(self, quit_cb):
        '''/v2/list_applications should not contain NoDisplay app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                response['payload'],
                Not(Contains(
                    ContainsDict({
                        'applicationId': Equals('org.test.VideoApp'),
                        'displayName': Equals('Video App'),
                        'shortDescription': Equals('A description about a Video App'),
                        'icon': matches_uri_query('/v2/application_icon', {
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
                                                   'list_applications',
                                                   version='v2'),
                                    {},
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_list_application_sets_drop_caches(self, quit_cb):
        '''/v2/list_application_sets handles Flatpak installation state changes.'''
        def cleanup_then_quit(exception=None):
            '''Cleanup the modified application metadata, then quit.'''
            modify_app_runtime(self.__class__.flatpak_installation_dir,
                               'org.test.VideoApp',
                               'com.endlessm.apps.Platform',
                               '3',
                               'com.endlessm.apps.Sdk',
                               '3',
                               lambda _, __: quit_cb(exception=exception))

        def query_side_effect(application_listing, query, cancellable, callback):
            '''Pass an empty array to the callback.'''
            del application_listing
            del query
            del cancellable

            GLib.idle_add(callback, None, [[], []])

        def on_second_query_done(*args):
            '''Called when the second query has completed.

            Assert that we used EknServices3 instead now because the
            detected runtime version changed (i.e, that the installation
            caches were cleared).
            '''
            del args

            # pylint: disable=unsubscriptable-object
            application_listing = connection.query.call_args[0][0]
            self.assertThat(application_listing.eknservices_name,
                            Equals('EknServices3'))

        def on_contents_replaced(*args):
            '''Called when the contents of the .changed file are been replaced.

            Trigger another query after a timeout (to account for a slight race
            between when the .changed file is updated and when the file monitor
            signal is triggered).
            '''
            del args

            GLib.timeout_add(
                100,
                lambda: json_http_request_with_uuid(
                    FAKE_UUID,
                    local_endpoint(self.port,
                                   'list_application_sets',
                                   version='v2'),
                    {
                        'applicationId': 'org.test.VideoApp'
                    },
                    handle_json(autoquit(on_second_query_done,
                                         cleanup_then_quit))
                )
            )

        def on_first_query_done(*args):
            '''Called when the first query is completed.

            Clear the flatpak installation state and change the metadata
            of the video app, with a sanity check that we used EknServices2.
            '''
            del args

            # pylint: disable=unsubscriptable-object
            application_listing = connection.query.call_args[0][0]
            self.assertThat(application_listing.eknservices_name,
                            Equals('EknServices2'))

            modify_app_runtime(self.__class__.flatpak_installation_dir,
                               'org.test.VideoApp',
                               'com.endlessm.apps.Platform',
                               '4',
                               'com.endlessm.apps.Sdk',
                               '4',
                               quit_on_fail(on_contents_replaced,
                                            cleanup_then_quit))

        connection = FakeContentDbConnection(FAKE_SHARD_CONTENT)
        connection.query = Mock(side_effect=query_side_effect)
        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           connection)
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(quit_on_fail(on_first_query_done,
                                                             cleanup_then_quit)))

    @with_main_loop
    def test_list_applications_error_no_device_uuid(self, quit_cb):
        '''/v2/list_applications should return an error if deviceUUID not set.'''
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
                                                   'list_applications',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app(self, quit_cb):
        '''/v2/application_icon should work for video app.'''
        def on_received_response(_, headers):
            '''Called when we receive a response from the server.'''
            self.assertEqual(headers.get_content_type()[0], 'image/png')

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_icon',
                                                   version='v2'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_headers_bytes(autoquit(on_received_response,
                                                                  quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_device_uuid(self, quit_cb):
        '''/v2/application_icon should return an error if deviceUUID not set.'''
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
                                                   'application_icon',
                                                   version='v2'),
                                    {
                                        'iconName': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_no_icon_name(self, quit_cb):
        '''/v2/application_icon should return an error if iconName not set.'''
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
                                                   'application_icon',
                                                   version='v2'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_icon_video_app_error_bad_icon_name(self, quit_cb):
        '''/v2/application_icon should return an error if iconName is not valid.'''
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
        '''/v2/application_colors should work for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['colors'],
                            MatchesSetwise(Equals('#4573d9'), Equals('#98b8ff')))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT))
        json_http_request_with_uuid(FAKE_UUID,
                                    local_endpoint(self.port,
                                                   'application_colors',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_device_uuid(self, quit_cb):
        '''/v2/application_colors should return an error if deviceUUID not set.'''
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
                                                   'application_colors',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_no_application_id(self, quit_cb):
        '''/v2/application_colors should return an error if applicationId not set.'''
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
                                                   'application_colors',
                                                   version='v2'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_colors_video_app_error_bad_application_id(self, quit_cb):
        '''/v2/application_colors should return an error if applicationId is not valid.'''
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
                                                   'application_colors',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_colors(self, quit_cb):
        '''/v2/list_application_sets should include colors.'''
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
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_home_page_tag(self, quit_cb):
        '''/v2/list_application_sets should return EknHomePageTag for video app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(response['payload']['sets'][0], ContainsDict({
                'tags': MatchesSetwise(Equals('EknHomePageTag')),
                'title': Equals('Video App'),
                'contentType': Equals('application/x-ekncontent-set'),
                'thumbnail': matches_uri_query('/v2/application_icon', {
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
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_content_app(self, quit_cb):
        '''/v2/list_application_sets should return correct tags for content app.'''
        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertThat(
                sorted(response['payload']['sets'], key=lambda s: s['title'])[0],
                ContainsDict({
                    'tags': MatchesSetwise(Equals('First Tag')),
                    'title': Equals('First Tag Set'),
                    'contentType': Equals('application/x-ekncontent-set'),
                    'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'list_application_sets',
                                                   version='v2'),
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
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_no_application_id(self, quit_cb):
        '''/v2/list_application_sets should return an error if applicationId not set.'''
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
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_sets_video_app_error_bad_application_id(self, quit_cb):
        '''/v2/list_application_sets should return an error if applicationID is not valid.'''
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
                                                   'list_application_sets',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.this.App.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_home_page_tag(self, quit_cb):
        '''/v2/list_application_content_for_tags returns video content listing.'''
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
                'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'list_application_content_for_tags',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_device_uuid(self, quit_cb):
        '''/v2/list_application_content_for_tags should return an error if deviceUUID not set.'''
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
        '''/v2/list_application_content_for_tags should return an error if applicationId not set.'''
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
                                                   'list_application_content_for_tags',
                                                   version='v2'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_no_tags(self, quit_cb):
        '''/v2/list_application_content_for_tags should return an error if tags not set.'''
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
                                                   'list_application_content_for_tags',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_application_content_for_tags_video_app_error_bad_application_id(self, quit_cb):
        '''/v2/list_application_sets should return an error if applicationID is not valid.'''
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
                                                   'list_application_content_for_tags',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.this.App.DNE',
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_get_content_metadata_video_app(self, quit_cb):
        '''/v2/content_metadata returns some expected video content metadata.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_metadata returns an error if deviceUUID is not set.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_metadata returns an error if applicationId is not set.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_metadata returns an error if contentId is not set.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_metadata returns an error applicationId is not valid.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_metadata returns an error contentId is not valid.'''
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
                                                       'content_metadata',
                                                       version='v2'),
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
        '''/v2/content_data returns some expected video content data.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns rewritten content app data.'''
        def on_received_response(msg_bytes, headers):
            '''Called when we receive a response from the server.'''
            body = msg_bytes.get_data().decode('utf-8')

            self.assertTrue(re.match(r'^.*<img src="\/v2/content_data.*$',
                                     body,
                                     flags=re.MULTILINE | re.DOTALL) != None)

            self.assertEqual(headers.get_content_length(), len(body))
            self.assertEqual(headers.get_content_type()[0], 'text/html')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns some expected partial video content data.'''
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
                                                       'content_data',
                                                       version='v2'),
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
    def test_get_content_data_video_app_cancel(self, quit_cb):
        '''/v2/content_data when cancelled returns error.'''
        def cancel_route_middleware(cancel_path):
            '''Middleware to cancel certain routes after initial request.'''
            def _apply(handler):
                '''Apply middleware.'''
                def _handler(server, msg, path, *args):
                    '''Request interceptor.

                    Handle the request as usual, then cancel it before
                    we get a chance to load any data.
                    '''
                    handler(server, msg, path, *args)
                    if path == cancel_path:
                        msg.cancellable.cancel()

                return _handler
            return _apply

        def on_received_response(response):
            '''Called when we receive a response from the server.'''
            self.assertTrue(response['status'] == 'error')
            self.assertTrue(response['error']['code'] == 'CANCELLED')

        def on_received_ekn_id(ekn_id):
            '''Make a query using the EKN ID.'''
            json_http_request_with_uuid(FAKE_UUID,
                                        local_endpoint(self.port,
                                                       'content_data',
                                                       version='v2'),
                                        {
                                            'applicationId': 'org.test.ContentApp',
                                            'contentId': ekn_id
                                        },
                                        handle_json(autoquit(on_received_response,
                                                             quit_cb)))

        self.service = CompanionAppService(Holdable(),
                                           self.port,
                                           FakeContentDbConnection(FAKE_SHARD_CONTENT),
                                           middlewares=[
                                               cancel_route_middleware('/v2/content_data')
                                           ])
        fetch_first_content_id('org.test.ContentApp',
                               ['First Tag'],
                               self.port,
                               on_received_ekn_id,
                               quit_cb)

    @with_main_loop
    def test_get_content_data_video_app_error_no_device_uuid(self, quit_cb):
        '''/v2/content_data returns an error if deviceUUID is not set.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns an error if applicationId is not set.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns an error if contentId is not set.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns an error applicationId is not valid.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/content_data returns an error contentId is not valid.'''
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
                                                       'content_data',
                                                       version='v2'),
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
        '''/v2/search_content is able to find content by applicationId.'''
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
                    'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.VideoApp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_tags(self, quit_cb):
        '''/v2/search_content is able to find content by tags.'''
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
                    'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'tags': 'EknHomePageTag'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term(self, quit_cb):
        '''/v2/search_content is able to find content by searchTerm.'''
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
                        'thumbnail': matches_uri_query('/v2/content_data', {
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
                        'thumbnail': matches_uri_query('/v2/content_data', {
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
                        'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'searchTerm': 'Sampl'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term_broken_app(self, quit_cb):
        '''/v2/search_content is able to find content even if an app is broken.

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
                        'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'searchTerm': 'Sampl'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_by_search_term_no_nodisplay_app(self, quit_cb):
        '''/v2/search_content does not include content from NoDisplay apps.'''
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'searchTerm': 'NoDisp'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_limit_and_offset(self, quit_cb):
        '''/v2/search_content is able to apply limits and offsets.'''
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
                        'thumbnail': matches_uri_query('/v2/content_data', {
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'searchTerm': 'Sampl',
                                        'offset': 1,
                                        'limit': 1
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_applications(self, quit_cb):
        '''/v2/search_content is able to search for applications.'''
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'searchTerm': 'Content'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_no_filters(self, quit_cb):
        '''/v2/search_content returns an error if no filters specified.'''
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_search_content_error_bad_app_id(self, quit_cb):
        '''/v2/search_content returns an error if invalid applicationId is specified.'''
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
                                                   'search_content',
                                                   version='v2'),
                                    {
                                        'applicationId': 'org.test.This.DNE'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_feed_endpoint(self, quit_cb):
        '''/v2/feed returns the expected content feed from the fake models.'''
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
                                                   'feed',
                                                   version='v2'),
                                    {
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))

    @with_main_loop
    def test_feed_no_mode_invalid(self, quit_cb):
        '''/v2/feed returns INVALID_REQUEST if no mode is specified.'''
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
                                'icon': matches_uri_query('/v2/application_icon', {
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
                                'icon': matches_uri_query('/v2/application_icon', {
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
                                'thumbnail': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(
                                        Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                                    ),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(Equals('sample_article_1')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID)),
                                    'referrer': MatchesSetwise(Equals('feed'))
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
                                'thumbnail': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(
                                        Equals(CONTENT_APP_THUMBNAIL_EKN_ID)
                                    ),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.ContentApp')),
                                    'contentId': MatchesSetwise(Equals('sample_article_2')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID)),
                                    'referrer': MatchesSetwise(Equals('feed'))
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
                                'thumbnail': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                                    'contentId': MatchesSetwise(Equals(VIDEO_APP_THUMBNAIL_EKN_ID)),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID))
                                }),
                                'uri': matches_uri_query('/v2/content_data', {
                                    'applicationId': MatchesSetwise(Equals('org.test.VideoApp')),
                                    'contentId': MatchesSetwise(Equals('sample_video_1')),
                                    'deviceUUID': MatchesSetwise(Equals(FAKE_UUID)),
                                    'referrer': MatchesSetwise(Equals('feed'))
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
                                                   'feed',
                                                   version='v2'),
                                    {
                                        'mode': 'ascending'
                                    },
                                    handle_json(autoquit(on_received_response,
                                                         quit_cb)))
