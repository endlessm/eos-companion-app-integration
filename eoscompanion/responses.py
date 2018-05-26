# /eoscompanion/responses.py
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
'''Response handling functions eoscompanion.'''

import json

from gi.repository import (
    EosCompanionAppService,
    GLib,
    Soup
)


def serialize_error_as_json_object(domain, code, detail=None):
    '''Serialize a GLib.Error as a JSON object.'''
    return {
        'domain': GLib.quark_to_string(domain),
        'code': code.value_nick.replace('-', '_').upper(),
        'detail': detail or {}
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


def custom_response(msg, content_type, content_bytes):
    '''Respond with :content_type: using :content_bytes:.'''
    msg.set_status(Soup.Status.OK)
    EosCompanionAppService.set_soup_message_response_bytes(msg,
                                                           content_type,
                                                           content_bytes)


def error_response(msg, domain, code, detail=None):
    '''Respond with an error with status code 200.'''
    msg.set_status(Soup.Status.OK)
    error = serialize_error_as_json_object(
        domain,
        code,
        detail=detail
    )
    return json_response(msg, {
        'status': 'error',
        'error': error
    })


def not_found_response(msg, path):
    '''Respond with an error message and 404.'''
    msg.set_status(Soup.Status.NOT_FOUND)
    error = serialize_error_as_json_object(
        EosCompanionAppService.error_quark(),
        EosCompanionAppService.Error.INVALID_REQUEST,
        detail={
            'invalid_path': path
        }
    )
    EosCompanionAppService.set_soup_message_response(msg,
                                                     'application/json',
                                                     json.dumps({
                                                         'status': 'error',
                                                         'error': error
                                                     }))
