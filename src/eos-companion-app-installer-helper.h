/* Copyright 2017 Endless Mobile, Inc.
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

#include <glib.h>
#include <gmodule.h>

/**
 * EOS_COMPANION_APP_OFFLINE_INSTALLER_ERROR:
 *
 * Error domain for EosCompanionAppOfflineInstaller.
 */
#define EOS_COMPANION_APP_OFFLINE_INSTALLER_ERROR (eos_companion_app_offline_installer_error_quark ())

GQuark eos_companion_app_offline_installer_error_quark (void);
