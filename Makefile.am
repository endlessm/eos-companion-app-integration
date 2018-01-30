# Copyright (C) 2017-2018 Endless Mobile, Inc.
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
# Note that this file includes Makefile.am.integration.inc for the Companion App
# OS Integration, which is installed as part of the base OS image and includes
# things like systemd services, and Makefile.am.service.inc for the Companion App
# Service, which is installed separately as a Flatpak.
#
# We define all automake variables first and then include the parts of the
# library that we are building. If you just intend to install globally
# on a developer system, you will need to pass --enable-integration, since
# --enable-service is the default

lib_LTLIBRARIES =
libexec_PROGRAMS =
libexec_SCRIPTS =
bin_SCRIPTS =

appdir = $(pythondir)/eoscompanion
app_PYTHON = 
configdir = $(datadir)/eos-companion-app
config_DATA = 
dbusservicedir = $(datadir)/dbus-1/services
dbusservice_DATA = 
dbussystemservicedir = $(datadir)/dbus-1/system-services
dbussystemservice_DATA = 
dbussystemconfdir = $(datadir)/dbus-1/system.d
dbussystemconf_DATA = 
girdir = $(datadir)/gir-1.0
gir_DATA = 
typelibdir = $(libdir)/girepository-1.0
typelib_DATA =
rulesdir = $(datadir)/polkit-1/rules.d
systemdserviceunitdir = $(libdir)/systemd/system/
systemdserviceunit_DATA = 
# systemsystemunitdir is defined by configure.ac
systemdsystemunit_DATA = 
systemdsysusersdir= $(libdir)/sysusers.d
systemdsysusers_DATA = 
tmpfilesdir = $(prefix)/lib/tmpfiles.d
tmpfiles_DATA = 

BUILT_SOURCES = 
CLEANFILES = 
EXTRA_DIST = 

# GObject Introspection setup
include $(INTROSPECTION_MAKEFILE)
INTROSPECTION_GIRS = $(NULL)
INTROSPECTION_SCANNER_ARGS = --add-include-path=$(srcdir) --warn-all
INTROSPECTION_COMPILER_ARGS = --includedir=$(srcdir)

# Make sure to pass the enable/disable switches to distcheck
AM_DISTCHECK_CONFIGURE_FLAGS = \
	$(ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS) \
	$(NULL)

include $(top_srcdir)/Makefile.am.service.inc
include $(top_srcdir)/Makefile.am.integration.inc

# Add GObject Introspection files to the build
gir_DATA += $(INTROSPECTION_GIRS)
typelib_DATA += $(INTROSPECTION_GIRS:.gir=.typelib)

CLEANFILES += $(gir_DATA) $(typelib_DATA)
