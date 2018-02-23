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
# This Makefile contains all the build rules for the "Service" parts
# of the Companion App enabled by default, disabled with --disable-service. It
# is installed as part of the Flatpak build in
# com.endlessm.CompanionAppService.json. It includes:
#
# - python HTTP server
# - integration library
# - GObject Introspection for the integration library

if EOS_COMPANION_APP_SERVICE_ENABLED
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
	libeoscompanion-dbus-1.la \
	libeoscompanion-1.la \
	$(NULL)

# DBus-activation
dbusservice_DATA += \
	data/com.endlessm.CompanionAppService.service

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
	$(EOS_COMPANION_APP_SERVICE_CFLAGS) \
	$(NULL)

libeoscompanion_dbus_1_la_LIBADD = \
	$(EOS_COMPANION_APP_SERVICE_LIBS) \
	$(NULL)

# Companion App Helper Library
dist_libeoscompanion_1_la_SOURCES = \
	src/eos-companion-app-integration-helper.c \
	src/eos-companion-app-integration-helper.h \
	$(NULL)

nodist_libeoscompanion_1_la_SOURCES = \
	src/config.h \
	$(enum_sources) \
	$(NULL)

libeoscompanion_1_la_CPPFLAGS = \
	$(EOS_COMPANION_APP_SERVICE_CFLAGS) \
	-I$(abs_top_builddir)/src \
	$(NULL)

libeoscompanion_1_la_LIBADD = \
	$(EOS_COMPANION_APP_SERVICE_LIBS) \
	$(NULL)

# Wrapper script
bin/eos-companion-app-service: bin/eos-companion-app-service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@libdir[@]|${libdir}|g;s|@pkgdatadir[@]|${pkgdatadir}|g;s|@pythonminorversion[@]|${pythonminorversion}|g' $< > $@.tmp && mv $@.tmp $@

CLEANFILES += bin/eos-companion-app-service
EXTRA_DIST += bin/eos-companion-app-service.in

# # # D-BUS SERVICES # # #
data/com.endlessm.CompanionAppService.service: data/com.endlessm.CompanionAppService.service.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@bindir[@]|${bindir}|g' $< > $@.tmp && mv $@.tmp $@

EXTRA_DIST += \
	data/com.endlessm.CompanionAppService.service.in \
	$(NULL)
CLEANFILES += \
	data/com.endlessm.CompanionAppService.service \
	$(NULL)

# # # D-BUS CODEGEN # # #
eos-companion-app-service-dbus.c: data/com.endlessm.CompanionAppService.xml
	$(AM_V_GEN)gdbus-codegen --generate-c-code eos-companion-app-service-dbus --c-namespace EosCompanionAppService --interface-prefix com.endlessm.CompanionApp. --output-directory=$(abs_top_builddir) $<

eos-companion-app-service-dbus.h: eos-companion-app-service-dbus.c

BUILT_SOURCES += $(gdbus_generated)
CLEANFILES += $(gdbus_generated)
EXTRA_DIST += data/com.endlessm.CompanionAppService.xml

# # # CONFIG FILE # # #
src/config.h: src/config.h.in
	$(AM_V_GEN) mkdir -p `dirname $@` && sed -e 's|@systemflatpakinstalldir[@]|${SYSTEM_INSTALL_DIR}|g;s|@externalflatpakinstalldir[@]|${EXTERNAL_INSTALL_DIR}|g;' $< > $@.tmp && mv $@.tmp $@

BUILT_SOURCES += src/config.h
CLEANFILES += src/config.h
EXTRA_DIST += src/config.h.in

# XXX: We need to touch the output file first while
# we wait for the version of glib that has https://github.com/endlessm/glib/commit/d8aee2cf5b150659928984de04c655dc06439b9c
# is picked into the runtime.
#
# # # ENUM HEADER FILES # # #
src/enums.h: $(enum_template_h_file) $(enum_header_files)
	$(AM_V_GEN) mkdir -p `dirname $@` && touch $@ && $(GLIB_MKENUMS) --template=$(abs_top_srcdir)/$(enum_template_h_file) $(enum_header_files) --output $(abs_top_builddir)/$@

src/enums.c: $(enum_template_c_file) $(enum_header_files) src/enums.h
	$(AM_V_GEN) mkdir -p `dirname $@` && touch $@ &&  $(GLIB_MKENUMS) --template=$(abs_top_srcdir)/$(enum_template_c_file) $(enum_header_files) --output $(abs_top_builddir)/$@

BUILT_SOURCES += $(enum_sources)
CLEANFILES += $(enum_sources)
EXTRA_DIST += $(enum_template_h_file) $(enum_template_c_file)

# # # GOBJECT INTROSPECTION FOR COMPANION APP SERVICE # # #
if HAVE_INTROSPECTION
introspection_sources = \
	$(gdbus_generated) \
	$(dist_libeoscompanion_1_la_SOURCES) \
	$(nodist_libeoscompanion_1_la_SOURCES) \
	$(NULL)

EosCompanionAppService-1.0.gir: libeoscompanion-dbus-1.la libeoscompanion-1.la
EosCompanionAppService_1_0_gir_INCLUDES = EosShard-0 GObject-2.0 Gio-2.0 GLib-2.0 Soup-2.4
EosCompanionAppService_1_0_gir_CFLAGS = $(EOS_COMPANION_APP_SERVICE_CFLAGS)
EosCompanionAppService_1_0_gir_LIBS = libeoscompanion-dbus-1.la libeoscompanion-1.la
EosCompanionAppService_1_0_gir_FILES = $(introspection_sources)

INTROSPECTION_GIRS += EosCompanionAppService-1.0.gir
endif

# # # TESTING # # #
if EOS_COMPANION_APP_SERVICE_ENABLE_TESTING
python_tests = \
	test/test_service.py \
	$(NULL)

test_data = \
	test_data/org.test.ContentApp/app/org.test.ContentApp.desktop \
	test_data/org.test.ContentApp/app/org.test.ContentApp.png \
	test_data/org.test.ContentApp/app/overrides.scss \
	test_data/org.test.ContentApp/content/article1.html \
	test_data/org.test.ContentApp/content/article2.html \
	test_data/org.test.ContentApp/content/thumbnail.jpg \
	test_data/org.test.ContentApp/content/image.jpg \
	test_data/org.test.ContentApp/content/db.json \
	test_data/org.test.VideoApp/app/org.test.VideoApp.desktop \
	test_data/org.test.VideoApp/app/org.test.VideoApp.png \
	test_data/org.test.VideoApp/app/overrides.scss \
	test_data/org.test.VideoApp/content/file.mp4 \
	test_data/org.test.VideoApp/content/thumbnail.jpg \
	test_data/org.test.VideoApp/content/db.json \
	$(NULL)

test_support = \
	test/__init__.py \
	test/build_app.py \
	$(NULL)

TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir):$${PYTHONPATH:+:$$PYTHONPATH}"; \
	export GI_TYPELIB_PATH="$(abs_top_builddir):$${GI_TYPELIB_PATH:+:$$GI_TYPELIB_PATH}"; \
	export LD_LIBRARY_PATH="$(abs_top_builddir)/.libs:$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}"; \
	export SOURCE_DIRECTORY="$(abs_top_srcdir)"; \
	export LC_ALL=C; \
	$(NULL)
TESTS = \
	$(python_tests) \
	$(NULL)

PY_LOG_COMPILER = $(abs_top_srcdir)/run-python-test.sh
AM_PY_LOG_FLAGS = -v

EXTRA_DIST += \
	$(python_tests) \
	$(test_data) \
	$(test_support) \
	./run-python-test.sh \
	$(NULL)
endif

endif
