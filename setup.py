# /setup.py
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
'''Installation and setup script for eoscompanion.'''

from setuptools import find_packages, setup

setup(name='eoscompanion',
      version='0.0.0',
      description='''OS Integration for Endless Companion App.''',
      long_description=('''
        OS Integration and Avahi services for Endless OS
        companion app.
      '''),
      author='Sam Spilsbury',
      author_email='sam@endlessm.com',
      classifiers=['Development Status :: 3 - Alpha',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.1',
                   'Programming Language :: Python :: 3.2',
                   'Programming Language :: Python :: 3.3',
                   'Programming Language :: Python :: 3.4',
                   'Intended Audience :: Developers',
                   'Topic :: System :: Shells',
                   'Topic :: Utilities'],
      url='http://github.com/endlessm/eos-companion-app-integration',
      license='MIT',
      keywords='development',
      packages=find_packages(exclude=['test']),
      install_requires=['setuptools'],
      test_suite='test',
      entry_points={
          'console_scripts': [
              'eos-companion-app-service=eoscompanion.main:main',
          ]
      },
      zip_safe=True,
      include_package_data=True)
