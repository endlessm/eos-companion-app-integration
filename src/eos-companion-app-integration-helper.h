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

#include <glib-object.h>

#include <avahi-gobject/ga-client.h>
#include <avahi-gobject/ga-entry-group.h>

#include <libsoup/soup.h>

G_BEGIN_DECLS

/**
 * EOS_COMPANION_APP_SERVICE_ERROR:
 *
 * Error doamin for EosCompanionAppService.
 */
#define EOS_COMPANION_APP_SERVICE_ERROR (eos_companion_app_service_error ())

/**
 * EosCompanionAppServiceError:
 * @EOS_COMPANION_APP_SERVICE_ERROR_INVALID_REQUEST: Invalid request made to service
 * @EOS_COMPANION_APP_SERVICE_ERROR_FAILED: Programmer or logic error on server side
 * @EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID: Provided App ID was not valid
 * @EOS_COMPANION_APP_SERVICE_ERROR_INVALID_CONTENT_ID: Provided Content ID was not valid
 *
 * Error codes for the %EOS_COMPANION_APP_SERVICE_ERROR error domain
 */
typedef enum {
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_REQUEST,
  EOS_COMPANION_APP_SERVICE_ERROR_FAILED,
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID,
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_CONTENT_ID
} EosCompanionAppServiceError;

GQuark eos_companion_app_service_error_quark (void);

gboolean eos_companion_app_service_add_avahi_service_to_entry_group (GaEntryGroup  *group,
                                                                     const gchar   *name,
                                                                     const gchar   *type,
                                                                     const gchar   *domain,
                                                                     const gchar   *host,
                                                                     guint          port,
                                                                     const gchar   *text,
                                                                     GError       **error);

void eos_companion_app_service_set_soup_message_response (SoupMessage *message,
                                                          const gchar *content_type,
                                                          const gchar *response);

void eos_companion_app_service_set_soup_message_request (SoupMessage *message,
                                                         const gchar *content_type,
                                                         const gchar *request);

gboolean eos_companion_app_service_soup_server_listen_on_sd_fd_or_port (SoupServer               *server,
                                                                        guint                     port,
                                                                        SoupServerListenOptions   options,
                                                                        GError                  **error);

G_END_DECLS

