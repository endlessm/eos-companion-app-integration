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

lib_LTLIBRARIES =
libexec_SCRIPTS =
bin_SCRIPTS =

appdir = $(pythondir)/eoscompanion
app_PYTHON = 
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

# Python files
app_PYTHON += \
	eoscompanion/__init__.py \
	eoscompanion/main.py \
	$(NULL)

# Wrapper script
bin_SCRIPTS += \
	bin/eos-companion-app-service \
	$(NULL)

# GDBus wrapper
lib_LTLIBRARIES += \
	libeoscompanion-avahi-helper-dbus-1.la \
	libeoscompanion-dbus-1.la \
	libeoscompanion-1.la \
	$(NULL)

# Helper scripts
libexec_SCRIPTS += \
	helper/eos-companion-app-avahi-helper \
	$(NULL)

# Necessary to get it included in the dist tarball
EXTRA_DIST += \
	helper/eos-companion-app-avahi-helper \
	$(NULL)

# DBus-activation
dbusservice_DATA += \
	data/com.endlessm.CompanionAppService.service

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

# systemd service for the Avahi Helper and the Companion App Service
systemdsystemunit_DATA += \
	data/eos-companion-app-avahi-helper.service \
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

enum_header_files = \
	src/eos-companion-app-integration-helper.h \
	$(NULL)
enum_template_h_file = src/enums.h.in
enum_template_c_file = src/enums.c.in
enum_sources = \
	src/enums.h \
	src/enums.c \
	$(NULL)

# Companion App D-Bus Library
gdbus_generated = \
	eos-companion-app-service-dbus.c \
	eos-companion-app-service-dbus.h \
	$(NULL)

nodist_libeoscompanion_dbus_1_la_SOURCES = \
	$(gdbus_generated) \
	$(NULL)

libeoscompanion_dbus_1_la_CPPFLAGS = \
	$(EOS_COMPANION_APP_CFLAGS) \
	$(NULL)

libeoscompanion_dbus_1_la_LIBADD = \
	$(EOS_COMPANION_APP_LIBS) \
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
	$(EOS_COMPANION_APP_CFLAGS) \
	$(NULL)

libeoscompanion_avahi_helper_dbus_1_la_LIBADD = \
	$(EOS_COMPANION_APP_LIBS) \
	$(NULL)

# Companion App Helper Library
libeoscompanion_1_la_SOURCES = \
	src/eos-companion-app-integration-helper.c \
	src/eos-companion-app-integration-helper.h \
	$(enum_sources) \
	$(NULL)

libeoscompanion_1_la_CPPFLAGS = \
	$(EOS_COMPANION_APP_CFLAGS) \
	$(NULL)

libeoscompanion_1_la_LIBADD = \
	$(EOS_COMPANION_APP_LIBS) \
	$(NULL)

# Wrapper script
bin/eos-companion-app-service: bin/eos-companion-app-service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libdir[@]|${libdir}|g;s|@pkgdatadir[@]|${pkgdatadir}|g;s|@pythonminorversion[@]|${pythonminorversion}|g' $< > $@.tmp && mv $@.tmp $@

CLEANFILES += bin/eos-companion-app-service
EXTRA_DIST += bin/eos-companion-app-service.in

# # # D-BUS SERVICES # # #
data/com.endlessm.CompanionAppService.service: data/com.endlessm.CompanionAppService.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@bindir[@]|${bindir}|g' $< > $@.tmp && mv $@.tmp $@

data/com.endlessm.CompanionAppServiceAvahiHelper.service: data/com.endlessm.CompanionAppServiceAvahiHelper.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libexecdir[@]|${libexecdir}|g' $< > $@.tmp && mv $@.tmp $@

# # # SYSTEMD SERVICES # # #
data/eos-companion-app-avahi-helper.service: data/eos-companion-app-avahi-helper.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libexecdir[@]|${libexecdir}|g' $< > $@.tmp && mv $@.tmp $@

CLEANFILES += \
	data/com.endlessm.CompanionAppService.service \
	data/com.endlessm.CompanionAppServiceAvahiHelper.service \
	$(NULL)
EXTRA_DIST += \
	data/com.endlessm.CompanionAppService.service.in \
	data/com.endlessm.CompanionAppServiceAvahiHelper.service.in \
	$(NULL)

# # # D-BUS CODEGEN # # #
eos-companion-app-service-dbus.c: data/com.endlessm.CompanionAppService.xml
	$(AM_V_GEN)gdbus-codegen --generate-c-code eos-companion-app-service-dbus --c-namespace EosCompanionAppService --interface-prefix com.endlessm.CompanionApp. --output-directory=$(abs_top_builddir) $<

eos-companion-app-service-dbus.h: eos-companion-app-service-dbus.c

BUILT_SOURCES += $(gdbus_generated)
CLEANFILES += $(gdbus_generated)
EXTRA_DIST += data/com.endlessm.CompanionAppService.xml

# # # D-BUS CODEGEN FOR AVAHI HELPER # # #
eos-companion-app-avahi-helper-dbus.c: data/com.endlessm.CompanionAppAvahiHelper.xml
	$(AM_V_GEN)gdbus-codegen --generate-c-code eos-companion-app-avahi-helper-dbus --c-namespace EosCompanionAppAvahiHelper --interface-prefix com.endlessm.CompanionApp. --output-directory=$(abs_top_builddir) $<

eos-companion-app-avahi-helper-dbus.h: eos-companion-app-avahi-helper-dbus.c

BUILT_SOURCES += $(avahi_helper_gdbus_generated)
CLEANFILES += $(avahi_helper_gdbus_generated)
EXTRA_DIST += data/com.endlessm.CompanionAppAvahiHelper.xml

# XXX: We need to touch the output file first while
# we wait for the version of glib that has https://github.com/endlessm/glib/commit/d8aee2cf5b150659928984de04c655dc06439b9c
# is picked into the runtime.
#
# # # ENUM HEADER FILES # # #
src/enums.h: $(enum_template_h_file) $(enum_header_files)
	$(AM_V_GEN) mkdir -p `dirname $@` && touch $@ && $(GLIB_MKENUMS) --template=$(enum_template_h_file) $(enum_header_files) --output $(abs_top_builddir)/$@

src/enums.c: $(enum_template_c_file) $(enum_header_files) src/enums.h
	$(AM_V_GEN) mkdir -p `dirname $@` && touch $@ &&  $(GLIB_MKENUMS) --template=$(enum_template_c_file) $(enum_header_files) --output $(abs_top_builddir)/$@

BUILT_SOURCES += $(enum_sources)
CLEANFILES += $(enum_sources)
EXTRA_DIST += $(enum_template_h_file) $(enum_template_c_file)

# # # GOBJECT_INTROSPECTION # # #
include $(INTROSPECTION_MAKEFILE)
INTROSPECTION_GIRS = $(NULL)
INTROSPECTION_SCANNER_ARGS = --add-include-path=$(srcdir) --warn-all
INTROSPECTION_COMPILER_ARGS = --includedir=$(srcdir)

if HAVE_INTROSPECTION
introspection_sources = \
	$(gdbus_generated) \
	$(libeoscompanion_1_la_SOURCES) \
	$(NULL)

EosCompanionAppService-1.0.gir: libeoscompanion-dbus-1.la libeoscompanion-1.la
EosCompanionAppService_1_0_gir_INCLUDES = GObject-2.0 Gio-2.0 GLib-2.0 Soup-2.4
EosCompanionAppService_1_0_gir_CFLAGS = $(INCLUDES)
EosCompanionAppService_1_0_gir_LIBS = libeoscompanion-dbus-1.la libeoscompanion-1.la
EosCompanionAppService_1_0_gir_FILES = $(introspection_sources)
INTROSPECTION_GIRS += EosCompanionAppService-1.0.gir

avahi_helper_introspection_sources = \
	$(avahi_helper_gdbus_generated) \
	$(NULL)

EosCompanionAppAvahiHelper-1.0.gir: libeoscompanion-avahi-helper-dbus-1.la
EosCompanionAppAvahiHelper_1_0_gir_INCLUDES = GObject-2.0 Gio-2.0 GLib-2.0
EosCompanionAppAvahiHelper_1_0_gir_CFLAGS = $(INCLUDES)
EosCompanionAppAvahiHelper_1_0_gir_LIBS = libeoscompanion-avahi-helper-dbus-1.la
EosCompanionAppAvahiHelper_1_0_gir_FILES = $(avahi_helper_introspection_sources)
INTROSPECTION_GIRS += EosCompanionAppAvahiHelper-1.0.gir

gir_DATA += $(INTROSPECTION_GIRS)
typelib_DATA += $(INTROSPECTION_GIRS:.gir=.typelib)

CLEANFILES += $(gir_DATA) $(typelib_DATA)
endif

# Install systemd unit files to the specified
# directory when doing 'make distcheck'.
AM_DISTCHECK_CONFIGURE_FLAGS = \
	--with-systemdsystemunit='$${prefix}/lib/systemd/system' \
	$(NULL)
