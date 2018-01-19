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
# This Makefile contains all the build rules for the "OS Integration" parts
# of the Companion App enabled with --enable-integration. It is installed
# as part of the embedded companion-app-os-integration debian package. It
# includes:
#
# - systemd service units
# - d-bus system bus service files
# - tmpfiles.d entries
# - sysusers.d entries
# - an "Avahi Helper" which updates the persistent state of discoverability
#   based on the Companion App's enable state
# - a boot time configuration manager that reads an installed configuration
#   file

if EOS_COMPANION_APP_INTEGRATION_ENABLED
# GDBus library for avahi helper
lib_LTLIBRARIES += \
	libeoscompanion-avahi-helper-dbus-1.la \
	$(NULL)

# Helper scripts
libexec_SCRIPTS += \
	helper/eos-companion-app-avahi-helper \
	$(NULL)

# Necessary to get it included in the dist tarball
EXTRA_DIST += \
	helper/eos-companion-app-avahi-helper \
	$(NULL)

# DBus System Service for Avahi Helper
dbussystemservice_DATA += \
	data/com.endlessm.CompanionAppServiceAvahiHelper.service \
	$(NULL)

# DBus System Service Configuration for Avahi Helper
dbussystemconf_DATA += \
	data/com.endlessm.CompanionAppServiceAvahiHelper.conf \
	$(NULL)

EXTRA_DIST += \
	data/com.endlessm.CompanionAppServiceAvahiHelper.conf \
	$(NULL)

# systemd service for the Avahi Helper, Companion App Service and Configuration
# Manager
systemdsystemunit_DATA += \
	data/eos-companion-app-avahi-helper.service \
	data/eos-companion-app-configuration-manager.service \
	data/eos-companion-app.service \
	data/eos-companion-app.socket \
	$(NULL)

EXTRA_DIST += \
	data/eos-companion-app-avahi-helper.service \
	data/eos-companion-app.service \
	data/eos-companion-app.socket \
	$(NULL)

# systemd sysusers.d entry for the companion-app-helper user
systemdsysusers_DATA += \
	data/eos-companion-app-helper-sysuser.conf \
	$(NULL)

EXTRA_DIST += \
	data/eos-companion-app-helper-sysuser.conf \
	$(NULL)

# tmpfiles entry for Avahi Helper
tmpfiles_DATA += \
	data/eos-companion-app-helper.conf \
	$(NULL)

EXTRA_DIST += \
	data/eos-companion-app-helper.conf \
	$(NULL)

# Companion App Avahi Helper D-Bus Library
avahi_helper_gdbus_generated = \
	eos-companion-app-avahi-helper-dbus.c \
	eos-companion-app-avahi-helper-dbus.h \
	$(NULL)

nodist_libeoscompanion_avahi_helper_dbus_1_la_SOURCES = \
	$(avahi_helper_gdbus_generated) \
	$(NULL)

libeoscompanion_avahi_helper_dbus_1_la_CPPFLAGS = \
	$(EOS_COMPANION_APP_INTEGRATION_CFLAGS) \
	$(NULL)

libeoscompanion_avahi_helper_dbus_1_la_LIBADD = \
	$(EOS_COMPANION_APP_INTEGRATION_LIBS) \
	$(NULL)

# Configuration Manager
libexec_PROGRAMS += eos-companion-app-configuration-manager

eos_companion_app_configuration_manager_SOURCES = \
	configuration-manager/main.c \
	$(NULL)

eos_companion_app_configuration_manager_CPPFLAGS = \
	-DDATADIR="\"$(datadir)\"" \
	-DLOCALSTATEDIR="\"$(localstatedir)\"" \
	-DSYSCONFDIR="\"$(sysconfdir)\"" \
	$(NULL)

eos_companion_app_configuration_manager_CFLAGS = \
	$(EOS_COMPANION_APP_INTEGRATION_CFLAGS) \
	$(NULL)
eos_companion_app_configuration_manager_LDADD = \
	$(EOS_COMPANION_APP_INTEGRATION_LIBS) \
	$(NULL)

# Configuration File Default
config_DATA += \
	data/config.ini \
	$(NULL)

EXTRA_DIST += data/config.ini

data/com.endlessm.CompanionAppServiceAvahiHelper.service: data/com.endlessm.CompanionAppServiceAvahiHelper.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libexecdir[@]|${libexecdir}|g' $< > $@.tmp && mv $@.tmp $@

EXTRA_DIST += \
	data/com.endlessm.CompanionAppServiceAvahiHelper.service.in \
	$(NULL)
CLEANFILES += \
	data/com.endlessm.CompanionAppServiceAvahiHelper.service \
	$(NULL)

# # # SYSTEMD SERVICES # # #
data/eos-companion-app-avahi-helper.service: data/eos-companion-app-avahi-helper.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libexecdir[@]|${libexecdir}|g' $< > $@.tmp && mv $@.tmp $@

data/eos-companion-app-configuration-manager.service: data/eos-companion-app-configuration-manager.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libexecdir[@]|${libexecdir}|g' $< > $@.tmp && mv $@.tmp $@

CLEANFILES += \
	data/eos-companion-app-avahi-helper.service \
	data/eos-companion-app-configuration-manager.service \
	$(NULL)
EXTRA_DIST += \
	data/eos-companion-app-avahi-helper.service.in \
	data/eos-companion-app-configuration-manager.service.in \
	$(NULL)

# # # D-BUS CODEGEN FOR AVAHI HELPER # # #
eos-companion-app-avahi-helper-dbus.c: data/com.endlessm.CompanionAppAvahiHelper.xml
	$(AM_V_GEN)gdbus-codegen --generate-c-code eos-companion-app-avahi-helper-dbus --c-namespace EosCompanionAppAvahiHelper --interface-prefix com.endlessm.CompanionApp. --output-directory=$(abs_top_builddir) $<

eos-companion-app-avahi-helper-dbus.h: eos-companion-app-avahi-helper-dbus.c

BUILT_SOURCES += $(avahi_helper_gdbus_generated)
CLEANFILES += $(avahi_helper_gdbus_generated)
EXTRA_DIST += data/com.endlessm.CompanionAppAvahiHelper.xml

# # # GOBJECT INTROSPECTION FOR AVAHI HELPER GDBUS GLUE # # #
if HAVE_INTROSPECTION
avahi_helper_introspection_sources = \
	$(avahi_helper_gdbus_generated) \
	$(NULL)

EosCompanionAppAvahiHelper-1.0.gir: libeoscompanion-avahi-helper-dbus-1.la
EosCompanionAppAvahiHelper_1_0_gir_INCLUDES = GObject-2.0 Gio-2.0 GLib-2.0
EosCompanionAppAvahiHelper_1_0_gir_CFLAGS = $(EOS_COMPANION_APP_SERVICE_CFLAGS)
EosCompanionAppAvahiHelper_1_0_gir_LIBS = libeoscompanion-avahi-helper-dbus-1.la
EosCompanionAppAvahiHelper_1_0_gir_FILES = $(avahi_helper_introspection_sources)

INTROSPECTION_GIRS += EosCompanionAppAvahiHelper-1.0.gir
endif

# Install systemd unit files to the specified
# directory when doing 'make distcheck'.
AM_DISTCHECK_CONFIGURE_FLAGS += \
	--with-systemdsystemunitdir='$${DESTDIR}$${prefix}/lib/systemd/system' \
	$(NULL)
endif
