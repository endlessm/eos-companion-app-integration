# /eoscompanion/dummy_feed.py
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
'''Function to provide a dummy feed.'''

def dummy_feed():
    '''Construct a dummy feed.'''
    return {
            'status': 'ok',
            'payload': [
                {
                    'sources': [
                        {
                            'type': 'application',
                            'detail': 'com.endlessm.celebrities.en',
                            'icon': '/v1/application_icon?deviceUUID=1234&iconName=com.endlessm.celebrities.en',
                            'displayName': 'Celebrities',
                            'shortDescription': 'Learn more about your favorite celebrities'
                        },
                        {
                            'type': 'application',
                            'detail': 'com.endlessm.wiki_art.en',
                            'icon': '/v1/application_icon?deviceUUID=1234&iconName=com.endlessm.wiki_art.en',
                            'displayName': 'WikiArt',
                            'shortDescription': 'A collection of great visual works'
                        },
                        {
                            'type': 'application',
                            'detail': 'com.endlessm.video_kids',
                            'icon': '/v1/application_icon?iconName=com.endlessm.video_kids&deviceUUID=1234',
                            'displayName': 'Kids',
                            'shortDescription': 'Kids will love these videos'
                        },
                        {
                            'type': 'application',
                            'detail': 'com.endlessm.word_of_the_day.en',
                            'displayName': 'Word of the day'
                        },
                        {
                            'type': 'application',
                            'detail': 'com.endlessm.quote_of_the_day.en',
                            'displayName': 'Quote of the day'
                        }
                    ],
                    'entries': [
                        {
                            'contentType': 'Article',
                            'source': [
                                {
                                    'type': 'application',
                                    'detail': [
                                        {
                                            'applicationId': 'com.endlessm.celebrities.en'
                                        }
                                    ]
                                }
                            ],
                            'detail': [
                                {
                                    'title': 'Lionel Messi',
                                    'synopis': '.',
                                    'thumbnail': '/v1/content_data?applicationId=com.endlessm.celebrities.en&deviceUUID=1234&contentId=7743ae136927867094cd8c3bffa0f13d5ef63696',
                                    'uri': '7b4978ba82ecf6b992c395956e0adad4b4734dbe'
                                }
                            ]
                        },
                        {
                            'contentType': 'Artwork',
                            'source': [
                                {
                                    'type': 'application',
                                    'detail': [
                                        {
                                            'applicationId': 'com.endlessm.wiki_art.en'
                                        }
                                    ]
                                }
                            ],
                            'detail': [
                                {
                                    'title': 'Madonna with Child',
                                    'synopis': '.',
                                    'thumbnail': '/v1/content_data?applicationId=com.endlessm.wiki_art.en&deviceUUID=1234&contentId=19db92f13325e93e4a7af18a997ed3941722c176',
                                    'uri': '7afc3eaf5805936f60404037112f08a41d0470cc'
                                }
                            ]
                        },
                        {
                            'contentType': 'Video',
                            'source': [
                                {
                                    'type': 'application',
                                    'detail': [
                                        {
                                            'applicationId': 'com.endlessm.video_kids'
                                        }
                                    ]
                                }
                            ],
                            'detail': [
                                {
                                    'title': 'Nice Crystal Ball Juggler in Europe',
                                    'thumbnail': '/v1/content_data?applicationId=com.endlessm.video_kids&deviceUUID=1234&contentId=3dfe56e4f28bacfebe9b7a800529dc9653267eff',
                                    'uri': 'bd794303e04e6d2bcc62858e47d813483056f88c',
                                    'duration': '121'
                                }
                            ]
                        },
                        {
                            'contentType': 'WordOfTheDay',
                            'source': [
                                {
                                    'type': 'application',
                                    'detail': [
                                        {
                                            'applicationId': 'com.endlessm.word_of_the_day.en'
                                        }
                                    ]
                                }
                            ],
                            'detail': [
                                {
                                    'word': 'spelunker',
                                    'partOfSpeech': 'noun',
                                    'definition': 'One who explores caves chiefly as a hobby; a caver.'
                                }
                            ]
                        },
                        {
                            'contentType': 'QuoteOfTheDay',
                            'source': [
                                {
                                    'type': 'application',
                                    'detail': [
                                        {
                                            'applicationId': 'com.endlessm.quote_of_the_day.en'
                                        }
                                    ]
                                }
                            ],
                            'detail': [
                                {
                                    'quote': 'Hitch your wagon to a star.',
                                    'author': 'Ralph Waldo Emerson (1803-1882)'
                                }
                            ]
                        }
                    ]
                }
            ]
           }
