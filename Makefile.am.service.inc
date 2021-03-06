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
	eoscompanion/applications_query.py \
	eoscompanion/constants.py \
	eoscompanion/content_streaming.py \
	eoscompanion/core_routes.py \
	eoscompanion/dummy_feed.py \
	eoscompanion/eknservices_bridge.py \
	eoscompanion/ekn_content_adjuster.py \
	eoscompanion/ekn_data.py \
	eoscompanion/ekn_query.py \
	eoscompanion/format.py \
	eoscompanion/functional.py \
	eoscompanion/license_content_adjuster.py \
	eoscompanion/main.py \
	eoscompanion/middlewares.py \
	eoscompanion/responses.py \
	eoscompanion/routes.py \
	eoscompanion/server.py \
	eoscompanion/service.py \
	eoscompanion/v1_routes.py \
	eoscompanion/v2_routes.py \
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

resources_sources = \
	src/eos-companion-app-service-resources.h \
	src/eos-companion-app-service-resources.c \
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
introspectable_dist_eoscompanion_sources = \
	src/eos-companion-app-integration-helper.c \
	src/eos-companion-app-integration-helper.h \
	src/eos-companion-app-service-app-info.c \
	src/eos-companion-app-service-app-info.h \
	src/eos-companion-app-service-managed-cache.c \
	src/eos-companion-app-service-managed-cache.h \
	$(NULL)

dist_libeoscompanion_1_la_SOURCES = \
	$(introspectable_dist_eoscompanion_sources) \
	src/eos-companion-app-service-managed-cache-private.h \
	$(NULL)

introspectable_nodist_eoscompanion_sources = \
	src/config.h \
	$(enum_sources) \
	$(NULL)

nodist_libeoscompanion_1_la_SOURCES = \
	$(introspectable_nodist_eoscompanion_sources) \
	$(resources_sources) \
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

# # # GRESOURCES # # #
src/eos-companion-app-service-resources.%: com.endlessm.CompanionAppService.gresource.xml
	$(AM_V_GEN) $(GLIB_COMPILE_RESOURCES) --generate $< --target=$@ --internal

BUILT_SOURCES += $(resources_sources)
CLEANFILES += $(resources_sources)
EXTRA_DIST += com.endlessm.CompanionAppService.gresource.xml

# # # GOBJECT INTROSPECTION FOR COMPANION APP SERVICE # # #
if HAVE_INTROSPECTION
introspection_sources = \
	$(gdbus_generated) \
	$(introspectable_dist_eoscompanion_sources) \
	$(introspectable_nodist_eoscompanion_sources) \
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
	test_data/org.test.ContentApp/app/app.gresource \
	test_data/org.test.ContentApp/app/org.test.ContentApp.desktop \
	test_data/org.test.ContentApp/app/org.test.ContentApp.png \
	test_data/org.test.ContentApp/app/overrides.scss \
	test_data/org.test.VideoApp/app/app.gresource \
	test_data/org.test.VideoApp/app/org.test.VideoApp.desktop \
	test_data/org.test.VideoApp/app/org.test.VideoApp.png \
	test_data/org.test.VideoApp/app/overrides.scss \
	$(NULL)

test_support = \
	test/__init__.py \
	test/build_app.py \
	test/routes_v1.py \
	test/routes_v2.py \
	test/service_test_helpers.py \
	$(NULL)

TESTS_ENVIRONMENT = \
	export EOS_COMPANION_APP_DISABLE_METRICS="1" \
	export EOS_COMPANION_APP_SERVICE_QUIET="1" \
	export PYTHONPATH="$(abs_top_srcdir):$${PYTHONPATH:+:$$PYTHONPATH}"; \
	export GI_TYPELIB_PATH="$(abs_top_builddir):$${GI_TYPELIB_PATH:+:$$GI_TYPELIB_PATH}"; \
	export LD_LIBRARY_PATH="$(abs_top_builddir)/.libs:$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}"; \
	export SOURCE_DIRECTORY="$(abs_top_srcdir)"; \
	export LC_ALL=C; \
	$(NULL)
TESTS = \
	$(python_tests) \
	run_pylint.pylint \
	$(NULL)

PY_LOG_COMPILER = $(abs_top_srcdir)/run-python-test.sh
AM_PY_LOG_FLAGS = -v

EXTRA_DIST += \
	$(python_tests) \
	$(test_data) \
	$(test_support) \
	run-python-test.sh \
	$(NULL)
endif

EOS_PYLINT_FILES = \
	$(app_PYTHON) \
	$(python_tests) \
	$(test_support) \
	$(NULL)

endif
