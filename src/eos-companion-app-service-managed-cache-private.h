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

#include "eos-companion-app-service-managed-cache.h"

G_BEGIN_DECLS

GHashTable * eos_companion_app_service_managed_cache_lock_subcache (EosCompanionAppServiceManagedCache *cache,
                                                                    const gchar                        *key,
                                                                    GDestroyNotify                      value_destroy);
void eos_companion_app_service_managed_cache_unlock_subcache (EosCompanionAppServiceManagedCache *cache,
                                                              const gchar                        *key);

G_END_DECLS
