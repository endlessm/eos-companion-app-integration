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

#include <glib-object.h>

G_BEGIN_DECLS

#define EOS_COMPANION_APP_SERVICE_TYPE_MANAGED_CACHE eos_companion_app_service_managed_cache_get_type ()
G_DECLARE_FINAL_TYPE (EosCompanionAppServiceManagedCache, eos_companion_app_service_managed_cache, EOS_COMPANION_APP_SERVICE, MANAGED_CACHE, GObject)

void eos_companion_app_service_managed_cache_clear (EosCompanionAppServiceManagedCache *cache);

EosCompanionAppServiceManagedCache * eos_companion_app_service_managed_cache_new (void);

G_END_DECLS
