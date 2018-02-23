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

import os
from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand
from subprocess import check_call


_CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
_BUILD_DIRECTORY = os.environ.get('BUILD_DIR', _CURRENT_DIRECTORY)


class SubprocessWrapperTestCommand(TestCommand):
    '''A wrapper to run tests in a subprocess with LD_LIBRARY_PATH.

    We need to use this since we depend on natively compiled modules
    in the build directory.
    '''
    def finalize_options(self):
        '''Save all options.'''
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        '''Run unittest in a subprocess.'''
        env = os.environ.copy()
        env.update({
            'LD_LIBRARY_PATH': os.pathsep.join([os.path.join(_BUILD_DIRECTORY,
                                                             '.libs'),
                                                os.environ.get('LD_LIBRARY_PATH',
                                                               '')]),
            'GI_TYPELIB_PATH': os.pathsep.join([os.path.join(_BUILD_DIRECTORY),
                                                os.environ.get('GI_TYPELIB_PATH',
                                                               '')]),
            'PYTHONPATH': os.pathsep.join([_CURRENT_DIRECTORY,
                                           os.environ.get('PYTHONPATH', '')]),
            'EOS_COMPANION_APP_DISABLE_METRICS': '1',
            'EOS_COMPANION_APP_SERVICE_QUIET': '1'
        })
        check_call(['python3',
                    '-m',
                    'unittest',
                    'discover',
                    '-v'],
                   cwd=os.path.join(_CURRENT_DIRECTORY, 'test'),
                   env=env)


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
      cmdclass={
          'test': SubprocessWrapperTestCommand
      },
      entry_points={
          'console_scripts': [
              'eos-companion-app-service=eoscompanion.main:main',
          ]
      },
      zip_safe=True,
      include_package_data=True)
