/* Copyright 2018 Endless Mobile, Inc.
 *
 * eos-companion-app-service is free software: you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License as
 * published by the Free Software Foundation, either version 2.1 of the
 * License, or (at your option) any later version.
 *
 * eos-companion-app-service is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with eos-companion-app-service.  If not, see
 * <http://www.gnu.org/licenses/>.
 */

#pragma once

#include <gio/gdesktopappinfo.h>
#include <glib-object.h>

G_BEGIN_DECLS

#define EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO eos_companion_app_service_app_info_get_type ()
G_DECLARE_FINAL_TYPE (EosCompanionAppServiceAppInfo, eos_companion_app_service_app_info, EOS_COMPANION_APP_SERVICE, APP_INFO, GObject)

GDesktopAppInfo * eos_companion_app_service_app_info_get_desktop_app_info (EosCompanionAppServiceAppInfo *info);
const gchar * eos_companion_app_service_app_info_get_eknservices_name (EosCompanionAppServiceAppInfo *info);
const gchar * eos_companion_app_service_app_info_get_search_provider_name (EosCompanionAppServiceAppInfo *info);

EosCompanionAppServiceAppInfo * eos_companion_app_service_app_info_new (GDesktopAppInfo *desktop_app_info,
                                                                        const gchar     *eknservices_name,
                                                                        const gchar     *search_provider_name);

G_END_DECLS


