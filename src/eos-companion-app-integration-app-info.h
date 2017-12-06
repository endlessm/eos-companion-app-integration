/*
 * Copyright © 2017 Endless Mobile, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library. If not, see <http://www.gnu.org/licenses/>.
 *
 * Authors:
 *       Sam Spilsbury <sam@endlessm.com>
 */

#pragma once

G_BEGIN_DECLS

#define EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO eos_companion_app_service_app_info_get_type ()
#define EOS_COMPANION_APP_SERVICE_APP_INFO(obj) (G_TYPE_CHECK_INSTANCE_CAST ((obj), EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO, EosCompanionAppServiceAppInfo))
#define EOS_COMPANION_APP_SERVICE_IS_APP_INFO(obj) (G_TYPE_CHECK_INSTANCE_TYPE ((obj), EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO))

typedef struct _EosCompanionAppServiceAppInfo EosCompanionAppServiceAppInfo;

GType eos_companion_app_service_app_info_get_type (void);

typedef struct _EosCompanionAppServiceAppInfo {
  GObject parent;
} EosCompanionAppServiceAppInfo;

typedef struct _EosCompanionAppServiceAppInfoClass {
  GObjectClass parent_class;
} EosCompanionAppServiceAppInfoClass;

EosCompanionAppServiceAppInfo * eos_companion_app_service_app_info_new (const gchar *app_id,
                                                                        const gchar *display_name);

G_DEFINE_AUTOPTR_CLEANUP_FUNC (EosCompanionAppServiceAppInfo, g_object_unref)

G_END_DECLS

