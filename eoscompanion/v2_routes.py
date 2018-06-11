# /eoscompanion/v2_routes.py
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
'''V2 route definitions for eos-companion-app-service.'''

from collections import defaultdict
import logging
import os


from gi.repository import (
    ContentFeed,
    EosCompanionAppService,
    GLib
)

from .applications_query import (
    application_listing_from_app_info
)
from .format import (
    format_app_icon_uri,
    format_content_data_uri,
    format_thumbnail_uri,
    parse_uri_path_basename
)
from .functional import all_asynchronous_function_calls_closure
from .middlewares import (
    add_content_db_conn,
    apply_version_to_all_routes,
    record_metric,
    require_query_string_param
)
from .responses import (
    json_response,
    respond_if_error_set
)
from .v1_routes import (
    companion_app_server_application_colors_route,
    companion_app_server_application_icon_route,
    companion_app_server_content_data_route,
    companion_app_server_content_metadata_route,
    companion_app_server_device_authenticate_route,
    companion_app_server_license_route,
    companion_app_server_list_application_content_for_tags_route,
    companion_app_server_list_application_sets_route,
    companion_app_server_list_applications_route,
    companion_app_server_resource_route,
    companion_app_server_search_content_route
)


def desktop_id_to_app_id(desktop_id):
    '''Remove .desktop suffix from desktop_id.'''
    return os.path.splitext(desktop_id)[0]


def yield_desktop_ids_from_feed_models(models):
    '''For each model that has a desktop_id, yield the desktop_id.'''
    for model in models:
        try:
            yield model.get_property('desktop-id')
        except TypeError:
            continue


def app_infos_for_feed_models(models, cancellable, callback):
    '''Get a GDesktopAppInfo for each model source in models.

    A source might have more than once model, so we deduplicate here.
    '''
    def _on_received_all_app_info_results(results):
        '''Callback for when all results are received.

        Check for errors and report them, ignoring sources that had errors.
        Continue with the sources that do not have errors.
        '''
        app_infos = []

        for result in results:
            error, info = result

            if error is not None:
                logging.error('Encountered error in getting app info: %s', error)
                continue

            app_infos.append(info)

        callback(None, app_infos)

    def _load_application_info_thunk(desktop_id):
        '''A thunk used here since we cannot use lambdas in for loops.'''
        def _internal(_load_app_info_callback):
            def _on_got_application_info(_, result):
                '''Marshal the error and result into a tuple.'''
                try:
                    info = application_listing_from_app_info(
                        EosCompanionAppService.finish_load_application_info(result)
                    )
                except GLib.Error as error:
                    _load_app_info_callback(error, None)
                    return

                _load_app_info_callback(None, info)

            application_id = desktop_id_to_app_id(desktop_id)
            EosCompanionAppService.load_application_info(application_id,
                                                         cancellable,
                                                         _on_got_application_info)

        return _internal

    desktop_ids = list(set([
        desktop_id for desktop_id in yield_desktop_ids_from_feed_models(models)
    ]))
    all_asynchronous_function_calls_closure([
        _load_application_info_thunk(desktop_id) for desktop_id in desktop_ids
    ], _on_received_all_app_info_results)


def sources_from_content_feed_models(models,
                                     version,
                                     query,
                                     cancellable,
                                     callback):
    '''Generate the "sources" entry for the feed JSON response.

    This response is a summary of all the sources that were queried in
    the feed. A source might generate multiple items to put in the feed
    so we can save some space in the payload by having a unique source
    identifier and specifying its detail once.

    Sources list generation happens asynchronously as it requires
    looking up desktop files.
    '''

    def _on_received_app_infos(error, app_infos):
        '''Called when we have our app_infos.

        We can now marshal each app_info into an 'application' source
        and continue using it that way.
        '''
        if error is not None:
            callback(error, None)
            return

        callback(None, [
            {
                'type': 'application',
                'detail': {
                    'applicationId': a.app_id,
                    'displayName': a.display_name,
                    'shortDescription': a.short_description,
                    'icon': format_app_icon_uri(version,
                                                a.icon,
                                                query['deviceUUID'])
                }
            }
            for a in app_infos
        ])

    app_infos_for_feed_models(models, cancellable, _on_received_app_infos)


_SOURCE_IDENTIFIER_KEYS_BY_TYPE = {
    'application': 'applicationId'
}


def get_source_identifier(source):
    '''Get the value of the source identifier key.'''
    return source['detail'][_SOURCE_IDENTIFIER_KEYS_BY_TYPE[source['type']]]


def _serialize_article_content_feed_model(model, app_id, version, query):
    '''Serialize the ARTICLE_CARD type content feed model.'''
    return [{
        'itemType': 'article',
        'source': {
            'type': 'application',
            'detail': {
                'applicationId': app_id
            },
        },
        'detail': {
            'title': model.get_property('title'),
            'synopsis': model.get_property('synopsis'),
            'thumbnail': format_thumbnail_uri(
                version,
                app_id,
                model.get_property('thumbnail-uri'),
                query['deviceUUID']
            ),
            'uri': format_content_data_uri(
                version,
                parse_uri_path_basename(model.get_property('uri')),
                app_id,
                query['deviceUUID'],
                # pylint: disable=no-member
                EosCompanionAppService.Referrer.FEED.value_nick
            ),
            'contentType': model.get_property('content-type')
        }
    }]


def maybe_get_property(model, prop_name):
    '''Get property if it exists, otherwise return None.'''
    try:
        return model.get_property(prop_name)
    except TypeError:
        return None


def _serialize_artwork_content_feed_model(model, app_id, version, query):
    '''Serialize the ARTWORK_CARD type content feed model.'''
    return [{
        'itemType': 'artwork',
        'source': {
            'type': 'application',
            'detail': {
                'applicationId': app_id
            },
        },
        'detail': {
            'title': model.get_property('title'),
            'author': model.get_property('author'),
            'firstDate': maybe_get_property(model, 'first-date'),
            'thumbnail': format_thumbnail_uri(
                version,
                app_id,
                model.get_property('thumbnail-uri'),
                query['deviceUUID']
            ),
            'uri': format_content_data_uri(
                version,
                parse_uri_path_basename(model.get_property('uri')),
                app_id,
                query['deviceUUID'],
                # pylint: disable=no-member
                EosCompanionAppService.Referrer.FEED.value_nick
            ),
            'contentType': model.get_property('content-type')
        }
    }]


def _serialize_video_content_feed_model(model, app_id, version, query):
    '''Serialize the VIDEO_CARD type content feed model.'''
    return [{
        'itemType': 'video',
        'source': {
            'type': 'application',
            'detail': {
                'applicationId': app_id
            },
        },
        'detail': {
            'title': model.get_property('title'),
            'thumbnail': format_thumbnail_uri(
                version,
                app_id,
                model.get_property('thumbnail-uri'),
                query['deviceUUID']
            ),
            'uri': format_content_data_uri(
                version,
                parse_uri_path_basename(model.get_property('uri')),
                app_id,
                query['deviceUUID'],
                # pylint: disable=no-member
                EosCompanionAppService.Referrer.FEED.value_nick
            ),
            'duration': model.get_property('duration'),
            'contentType': model.get_property('content-type')
        }
    }]


def _serialize_news_content_feed_model(model, app_id, version, query):
    '''Serialize the NEWS_CARD type content feed model.'''
    return [{
        'itemType': 'news',
        'source': {
            'type': 'application',
            'detail': {
                'applicationId': app_id
            },
        },
        'detail': {
            'title': model.get_property('title'),
            'synopsis': model.get_property('synopsis'),
            'thumbnail': format_thumbnail_uri(
                version,
                app_id,
                model.get_property('thumbnail-uri'),
                query['deviceUUID']
            ),
            'uri': format_content_data_uri(
                version,
                parse_uri_path_basename(model.get_property('uri')),
                app_id,
                query['deviceUUID'],
                # pylint: disable=no-member
                EosCompanionAppService.Referrer.FEED.value_nick
            ),
            'contentType': model.get_property('content-type')
        }
    }]


def _serialize_quote_content_feed_model(model):
    '''Serialize the QUOTE_CARD type content feed model.'''
    return {
        'itemType': 'quoteOfTheDay',
        'source': {
            'type': 'none',
            'detail': None,
        },
        'detail': {
            'quote': model.get_property('quote'),
            'author': model.get_property('author')
        }
    }


def _serialize_word_content_feed_model(model):
    '''Serialize the WORD_CARD type content feed model.'''
    return {
        'itemType': 'wordOfTheDay',
        'source': {
            'type': 'none',
            'detail': None,
        },
        'detail': {
            'word': model.get_property('word'),
            'partOfSpeech': model.get_property('part-of-speech'),
            'definition': model.get_property('definition')
        }
    }


def _serialize_word_quote_content_feed_model(model, *args):
    '''Serialize the WORD_QUOTE_CARD type content feed model.'''
    del args

    word_model = model.get_property('word')
    quote_model = model.get_property('quote')

    return [
        _serialize_word_content_feed_model(word_model),
        _serialize_quote_content_feed_model(quote_model)
    ]


_CONTENT_FEED_MODEL_SERIALIZERS = {
    ContentFeed.CardStoreType.ARTICLE_CARD: _serialize_article_content_feed_model,
    ContentFeed.CardStoreType.ARTWORK_CARD: _serialize_artwork_content_feed_model,
    ContentFeed.CardStoreType.VIDEO_CARD: _serialize_video_content_feed_model,
    ContentFeed.CardStoreType.NEWS_CARD: _serialize_news_content_feed_model,
    ContentFeed.CardStoreType.WORD_QUOTE_CARD: _serialize_word_quote_content_feed_model
}

def content_feed_model_to_json_entries(model, app_id, version, query):
    '''Return a list of json entries for each model.

    This varies depending on the model type. Some models may return
    more than one entry (for instance, the word-quote model returns
    two entries).
    '''
    return _CONTENT_FEED_MODEL_SERIALIZERS[model.get_property('type')](model,
                                                                       app_id,
                                                                       version,
                                                                       query)


def entries_from_content_feed_models(models, sources, version, query):
    '''Generate the "entries" entry for the feed JSON response.

    This response will contain every model in the models as long as
    the model type is known and its source was present in the sources
    entry.

    Problems with individual models will be reported on the console.
    '''
    # A map of sources, first by type and then by a unique identifier
    # for the source of that type. This is used to quickly lookup whether
    # an entry has a corresponding source.
    sources_map = defaultdict(set)

    for source in sources:
        sources_map[source['type']].add(get_source_identifier(source))

    for model in models:
        # Get the app ID for all content models that have a desktop ID. If
        # a content model does not have a desktop ID then we can still
        # display it, but the user won't be able to navigate to content
        # for that app.
        try:
            app_id = desktop_id_to_app_id(model.get_property('desktop-id'))
        except TypeError:
            app_id = None

        if app_id is not None and app_id not in sources_map['application']:
            logging.warning('Model %s with app-id %s did not have a '
                            'corresponding entry in the sources list, it will be '
                            'ignored', model, app_id)
            continue

        for entry in content_feed_model_to_json_entries(model,
                                                        app_id,
                                                        version,
                                                        query):
            yield entry


@require_query_string_param('deviceUUID')
@require_query_string_param('mode')
@record_metric('af3e89b2-8293-4703-809c-8e0231c128cb')
def companion_app_server_feed_route(server,
                                    msg,
                                    path,
                                    query,
                                    context,
                                    version,
                                    content_db_conn):
    '''Request the Content Feed from ContentFeed.

    The :mode: paramter is used to determine whether newer entries
    should be fetched or older entries should be fetched. It is currently
    unused for now, the feed is the same as the Discovery Feed on the
    desktop.
    '''
    del path
    del context

    def _on_received_ordered_feed_models(error, models):
        '''Callback for when the ordered feed models are ready.

        The models are in the exact order that they should be displayed
        in the feed, so we should marshal them into the appropriate
        JSON representation and display them now.
        '''
        def _on_received_sources(error, sources):
            '''Callback for when we work out the info for all the sources.'''
            if respond_if_error_set(msg, error):
                server.unpause_message(msg)
                return

            entries = list(entries_from_content_feed_models(models,
                                                            sources,
                                                            version,
                                                            query))
            json_response(msg, {
                'status': 'ok',
                'payload': {
                    'state': {
                        'sources': [
                        ],
                        'index': len(entries)
                    },
                    'sources': sources,
                    'entries': entries
                }
            })
            server.unpause_message(msg)

        if respond_if_error_set(msg, error):
            server.unpause_message(msg)
            return

        sources_from_content_feed_models(models,
                                         version,
                                         query,
                                         msg.cancellable,
                                         _on_received_sources)

    logging.debug('Feed: for clientId=%s', query['deviceUUID'])

    content_db_conn.feed(msg.cancellable, _on_received_ordered_feed_models)
    server.pause_message(msg)


def create_companion_app_routes_v2(content_db_conn):
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
        '/feed': add_content_db_conn(
            companion_app_server_feed_route,
            content_db_conn
        ),
        '/resource': companion_app_server_resource_route,
        '/license': companion_app_server_license_route
    }, 'v2')
