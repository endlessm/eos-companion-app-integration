# /eoscompanion/middlewares.py
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
'''Middlewares for eoscompanion.'''

import functools
import itertools

from gi.repository import EosCompanionAppService, EosMetrics, Gio, GLib, Soup

from .constants import INACTIVITY_TIMEOUT

from .responses import (
    json_response,
    not_found_response,
    serialize_error_as_json_object
)


def compose_middlewares(*middlewares):
    '''Compose middlewares from right to left.

    For instance, [f, g. x] gets composed as f(g(x)) (g first, then f).
    '''
    return functools.reduce(lambda x, f: f(x), reversed(middlewares))


def application_hold_middleware(application):
    '''Middleware function to put a hold on the application.

    This ensures that the application does not go away whilst we're handling
    HTTP traffic.

    Because we call org.freedesktop.login1.Inhibit at startup, the computer
    is guaranteed to be alive for INACTIVITY_TIMEOUT milliseconds after
    the response completes. In order to tell the client that, we take
    embed this information in a reponse header indicating that the
    server will be alive for a further INACTIVITY_TIMEOUT milliseconds
    after the response completes.
    '''
    def _apply(handler):
        '''Apply middleware to the handler.'''
        def _handler(server, msg, *args, **kwargs):
            '''Middleware function.'''
            application.hold()
            msg.get_property('response-headers').replace('X-Endless-Alive-For-Further',
                                                         str(INACTIVITY_TIMEOUT))
            msg.connect('finished', lambda _: application.release())
            return handler(server, msg, *args, **kwargs)

        return _handler

    return _apply


def handle_404_middleware(expected_path):
    '''Middleware function to return 404 if the path is not the expected one.

    Soup's documentation says that when a matching route is not
    found for a path, it will "strip path components one by one until
    it finds a matching handler." This behaviour isn't particularly
    desirable - if the route mismatches we should really just return
    a 404. The best way to detect this is if the invoked route does
    not match the path in the request.'''
    def _apply(handler):
        '''Apply middleware to the handler.'''
        def _handler(server, msg, path, query, *args):
            '''Middleware function.'''
            if path != expected_path:
                msg.set_status(Soup.Status.OK)
                not_found_response(msg, path)
                return None

            return handler(server, msg, path, query, *args)

        return _handler

    return _apply


def cancellability_middleware(handler):
    '''Middleware function to add cancellability to a request.

    This allocates a new GCancellable and sets it as an attribute
    of the message. The route can then use the cancellable accordingly.

    The cancellable itself is looked up on the signal handler for
    SoupServer::request-aborted if the client closes the connection
    before we have a chance to finish processing the response.
    '''
    def _handler(server, msg, *args):
        '''Middleware function.'''
        cancellable = Gio.Cancellable()
        setattr(msg, 'cancellable', cancellable)

        return handler(server, msg, *args)

    return _handler


def add_content_db_conn(route, content_db_conn):
    '''Partially apply content_db_conn to the end of route.'''
    def wrapper(*args, **kwargs):
        '''Call route with content_db_conn applied to the end.'''
        all_args = itertools.chain(args, [content_db_conn])
        return route(*all_args, **kwargs)

    return wrapper


def require_query_string_param(param):
    '''Require the uri to contain certain query parameter or raise.'''
    def decorator(handler):
        '''Decorate the actual function.'''
        def middleware(server, msg, path, query, *args):
            '''Middleware to check the query parameters.'''
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

            return handler(server, msg, path, rectified_query, *args)
        return middleware
    return decorator


def record_metric(metric_id):
    '''Middleware function to record all routes in the metrics system.

    This middleware records both the route and the relevant querystring
    encoded as a dictionary.
    '''
    def decorator(handler):
        '''Wrap the actual function.'''
        def middlware(server, msg, path, query, *args, **kwargs):
            '''Middleware function.'''
            if not GLib.getenv('EOS_COMPANION_APP_DISABLE_METRICS'):
                metrics = EosMetrics.EventRecorder.get_default()
                metrics.record_event(metric_id,
                                     GLib.Variant('a{ss}', dict(query or {})))

            return handler(server, msg, path, query, *args, **kwargs)

        return middlware

    return decorator


def apply_route_version(handler, route_version):
    '''Partially apply route_version to the end of handler.'''
    def wrapper(*args, **kwargs):
        '''Call route with route_version applied to the end.'''
        all_args = itertools.chain(args, [route_version])
        return handler(*all_args, **kwargs)

    return wrapper


def apply_version_to_all_routes(routes_dict, version):
    '''Apply version prefix to all routes and pass version to callbacks.

    This is so that if the route creates a URI for another route, it can create
    that URI on the same version.
    '''
    return {
        '/{version}{route}'.format(version=version,
                                   route=route): apply_route_version(callback,
                                                                     version)
        for route, callback in routes_dict.items()
    }
