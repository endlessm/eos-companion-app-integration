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
void eos_companion_app_service_set_soup_message_response_bytes (SoupMessage *message,
                                                                const gchar *content_type,
                                                                GBytes      *bytes);

void eos_companion_app_service_set_soup_message_request (SoupMessage *message,
                                                         const gchar *content_type,
                                                         const gchar *request);

gboolean eos_companion_app_service_soup_server_listen_on_sd_fd_or_port (SoupServer               *server,
                                                                        guint                     port,
                                                                        SoupServerListenOptions   options,
                                                                        GError                  **error);

/**
 * eos_companion_app_service_list_application_infos:
 * @cancellable: A #GCancellable
 * @callback: A #GAsyncReadyCallback
 *
 * Asynchronously query for all available content applications installed
 * on the system, by examining all search providers and pulling information
 * out of desktop files.
 */
void eos_companion_app_service_list_application_infos (GCancellable        *cancellable,
                                                       GAsyncReadyCallback  callback,
                                                       gpointer             user_data);

/**
 * eos_companion_app_service_finish_list_application_infos:
 * @result: A #GAsyncResult
 * @error: A #GErrror
 *
 * Complete the call to eos_companion_app_service_list_application_infos by returning
 * a pointer array of #GKeyFile with entries from the application's .desktop file.
 *
 * Note that we cannot return a GDesktopAppInfo since the application's binary
 * will not be in PATH in the sandbox.
 *
 * XXX: For some very strange reason, transferring the container to PyGI causes
 * it to immediately crash since it tries to unref the container straight away,
 * even though g_task_propagate_pointer is meant to be transfer full. Leak it
 * for now.
 *
 * Returns: (transfer none) (element-type GKeyFile): a #GPtrArray
            of #GKeyFile
 */
GPtrArray * eos_companion_app_service_finish_list_application_infos (GAsyncResult  *result,
                                                                     GError       **error);


/**
 * eos_companion_app_service_load_application_icon_data_async:
 * @icon_name: The name of the icon
 * @cancellable: A #GCancellable
 * @callback: A #GAsyncReadyCallback
 *
 * Asynchronously load icon data for the given icon name and pass it as a
 * #GBytes to the provided @callback.
 */
void eos_companion_app_service_load_application_icon_data_async (const gchar         *icon_name,
                                                                 GCancellable        *cancellable,
                                                                 GAsyncReadyCallback  callback,
                                                                 gpointer             user_data);

/**
 * eos_companion_app_service_finish_load_application_icon_data_async:
 * @result: A #GAsyncResult
 * @error: A #GErrror
 *
 * Complete the call to eos_companion_app_service_load_application_icon_data_from_data_dirs by returning
 * a #GBytes with PNG icon data.
 *
 * Returns: (transfer none): a #GBytes containing PNG data
 */
GBytes * eos_companion_app_service_finish_load_application_icon_data_async (GAsyncResult  *result,
                                                                            GError       **error);

G_END_DECLS

