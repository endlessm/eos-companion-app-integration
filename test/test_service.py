# /test/test_service.py
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
'''Tests for all route versions.'''

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
    FAKE_APPS,
    generate_flatpak_installation_directory,
    TEST_DATA_DIRECTORY,
    TestCompanionAppService
)

# pylint: disable=wrong-import-order
from test.routes_v1 import CompanionAppServiceRoutesV1


FLATPAK_INSTALLATION_DIR = None


# pylint: disable=invalid-name
def setUpModule():
    '''Set up the entire module by setting up fake apps.'''
    global FLATPAK_INSTALLATION_DIR  # pylint: disable=global-statement

    FLATPAK_INSTALLATION_DIR = generate_flatpak_installation_directory()
    setup_fake_apps(FAKE_APPS,
                    TEST_DATA_DIRECTORY,
                    FLATPAK_INSTALLATION_DIR)


# pylint: disable=invalid-name
def tearDownModule():
    '''Tear down the entire module by deleting the fake apps.'''
    force_remove_directory(FLATPAK_INSTALLATION_DIR)



# The following is a little confusing but there is a method to the madness.
#
# The core problem here is that we want to have a different TestCase subclass
# for both each route version so that we can keep the tests in separate
# files. However doing that will cause setUpClass and tearDownClass to be
# called once per route version, which confuses Gio's caching of things
# like desktop files.
#
# To get around this, we move that setup into the setUpModule and tearDownModule
# phase as above. However, this means that all the tests need to be in the
# same module to ensure that those functions are called once for all route
# tests. To do that, we define the tests themselves in pseudo-fixtures that
# are not normally discoverable in separate modules (keeps separatation of
# code between route versions), then import the class defining the tests
# and use inheritance to mix those with SetFlatpakInstallationDirMixin below
# and the TestCompanionAppService base fixture to create the actual discoverable
# TestCase subclass for that route version in this module.
#
# SetFlatpakInstallationDirMixin is a small helper that sets the
# flatpak_installation_dir attribute on the class from the global
# FLATPAK_INSTALLATION_DIR that would have been set earlier - the test helpers
# need it and the tests themselves need it and we can't reference that from the
# test helpers or the tests themselves as it would create an import cycle.
class SetFlatpakInstallationDirMixin(object):
    '''Mixin to set flatpak_installation_dir on the class at setUpClass.'''

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        '''Set the flatpak_installation_dir member then chain up.'''
        cls.flatpak_installation_dir = FLATPAK_INSTALLATION_DIR
        super(SetFlatpakInstallationDirMixin, cls).setUpClass()


class TestCompanionAppServiceV1Routes(SetFlatpakInstallationDirMixin,
                                      TestCompanionAppService,
                                      CompanionAppServiceRoutesV1):
    '''Tests for the /v1 routes.'''
    pass
