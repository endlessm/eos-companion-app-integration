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
                'state': {
                    'sources': [
                    ],
                    'index': 6
                 },
                 'sources': [
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.celebrities.en',
                                'icon': '/v1/application_icon?deviceUUID=1234&iconName=com.endlessm.celebrities.en',
                                'displayName': 'Celebrities',
                                'shortDescription': 'Learn more about your favorite celebrities'
                            }
                        ]
                    },
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.wiki_art.en',
                                'icon': '/v1/application_icon?deviceUUID=1234&iconName=com.endlessm.wiki_art.en',
                                'displayName': 'WikiArt',
                                'shortDescription': 'A collection of great visual works'
                            }
                        ]
                    },
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.video_kids',
                                'icon': '/v1/application_icon?iconName=com.endlessm.video_kids&deviceUUID=1234',
                                'displayName': 'Kids',
                                'shortDescription': 'Kids will love these videos'
                            }
                        ]
                    },
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.word_of_the_day.en',
                                'icon': '',
                                'displayName': 'Word of the day',
                                'shortDescription': ''
                            }
                        ]
                    },
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.quote_of_the_day.en',
                                'icon': '',
                                'displayName': 'Quote of the day',
                                'shortDescription': ''
                            }
                        ]
                    },
                    {
                        'type': 'application',
                        'detail': [
                            {
                                'applicationId': 'com.endlessm.okezone.id',
                                'icon': '/v1/application_icon?iconName=com.endlessm.okezone.id&deviceUUID=1234',
                                'displayName': 'Okezone',
                                'shortDescription': 'Aplikasi berita terkini'
                            }
                        ]
                    }
                ],
                'entries': [
                    {
                        'contentType': 'article',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.celebrities.en'
                                }
                            ]
                        },
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
                        'contentType': 'artwork',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.wiki_art.en'
                                }
                            ]
                        },
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
                        'contentType': 'video',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.video_kids'
                                }
                            ]
                        },
                        'detail': [
                            {
                                'title': 'Nice Crystal Ball Juggler in Europe',
                                'thumbnail': '/v1/content_data?applicationId=com.endlessm.video_kids&deviceUUID=1234&contentId=3dfe56e4f28bacfebe9b7a800529dc9653267eff',
                                'uri': 'bd794303e04e6d2bcc62858e47d813483056f88c',
                                'duration': '2:01'
                            }
                        ]
                    },
                    {
                        'contentType': 'wordOfTheDay',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.word_of_the_day.en'
                                }
                            ]
                        },
                        'detail': [
                            {
                                'word': 'spelunker',
                                'partOfSpeech': 'noun',
                                'definition': 'One who explores caves chiefly as a hobby; a caver.'
                            }
                        ]
                    },
                    {
                        'contentType': 'quoteOfTheDay',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.quote_of_the_day.en'
                                }
                            ]
                        },
                        'detail': [
                            {
                                'quote': 'Hitch your wagon to a star.',
                                'author': 'Ralph Waldo Emerson (1803-1882)'
                            }
                        ]
                    },
                    {
                        'contentType': 'news',
                        'source': {
                            'type': 'application',
                            'detail': [
                                {
                                    'applicationId': 'com.endlessm.okezone.id'
                                }
                            ]
                        },
                        'detail': [
                            {
                                'title': 'KY Pantau Sidang Perdana Setya Novanto di Pengadilan Tipikor',
                                'synopis': 'Pemantauan dilakukan secara terbuka ataupun tertutup - Nasional - Okezone News',
                                'thumbnail': '/v1/content_data?applicationId=com.endlessm.okezone.id&deviceUUID=1234&contentId=746733c3eec7611da24cb67f06f8b9ea00fefdd6',
                                'uri': '05237c7d516e57e1830fc9afc1e6ac8bb251dd50'
                            }
                        ]
                    }
                ]
            }
        ]
    }
