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

#include <gio/gdesktopappinfo.h>
#include <glib-object.h>

#include <eos-shard/eos-shard-blob.h>

#include <libsoup/soup.h>

#include "eos-companion-app-service-app-info.h"
#include "eos-companion-app-service-managed-cache.h"

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
 * @EOS_COMPANION_APP_SERVICE_ERROR_UNSUPPORTED: Caller asked for something that is not supported
 * @EOS_COMPANION_APP_SERVICE_ERROR_CANCELLED: Request was cancelled
 *
 * Error codes for the %EOS_COMPANION_APP_SERVICE_ERROR error domain
 */
typedef enum {
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_REQUEST,
  EOS_COMPANION_APP_SERVICE_ERROR_FAILED,
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID,
  EOS_COMPANION_APP_SERVICE_ERROR_INVALID_CONTENT_ID,
  EOS_COMPANION_APP_SERVICE_ERROR_UNSUPPORTED,
  EOS_COMPANION_APP_SERVICE_ERROR_CANCELLED
} EosCompanionAppServiceError;

GQuark eos_companion_app_service_error_quark (void);


/**
 * EosCompanionAppServiceReferrer:
 * @EOS_COMPANION_APP_SERVICE_REFERRER_FEED: Referred from content feed
 * @EOS_COMPANION_APP_SERVICE_REFERRER_SEARCH_CONTENT: Referred from content search
 * @EOS_COMPANION_APP_SERVICE_REFERRER_LIST_CONTENT_FOR_TAGS: Referred from list_application_content_for_tags
 * @EOS_COMPANION_APP_SERVICE_REFERRER_LIST_APPLICATIONS: Referred from list_applications
 * @EOS_COMPANION_APP_SERVICE_REFERRER_LIST_APLLICATION_SETS: Referred from list_application_sets
 * @EOS_COMPANION_APP_SERVICE_REFERRER_DEVICE_AUTHENTICATE: Referred from device_authenticate
 * @EOS_COMPANION_APP_SERVICE_REFERRER_REFRESH: Referred from refreshing a view
 * @EOS_COMPANION_APP_SERVICE_REFERRER_RETRY: Referred from retrying a connection
 * @EOS_COMPANION_APP_SERVICE_REFERRER_BACK: Referred from going back
 * @EOS_COMPANION_APP_SERVICE_REFERRER_CONTENT: Referred from following link in content
 *
 * Referrer types when navigating around the app. The referrer is the type of
 * view the user was last on when they requested a new view.
 */
typedef enum {
  EOS_COMPANION_APP_SERVICE_REFERRER_FEED,
  EOS_COMPANION_APP_SERVICE_REFERRER_SEARCH_CONTENT,
  EOS_COMPANION_APP_SERVICE_REFERRER_LIST_CONTENT_FOR_TAGS,
  EOS_COMPANION_APP_SERVICE_REFERRER_LIST_APPLICATIONS,
  EOS_COMPANION_APP_SERVICE_REFERRER_LIST_APLLICATION_SETS,
  EOS_COMPANION_APP_SERVICE_REFERRER_DEVICE_AUTHENTICATE,
  EOS_COMPANION_APP_SERVICE_REFERRER_REFRESH,
  EOS_COMPANION_APP_SERVICE_REFERRER_RETRY,
  EOS_COMPANION_APP_SERVICE_REFERRER_BACK,
  EOS_COMPANION_APP_SERVICE_REFERRER_CONTENT
} EosCompanionAppServiceReferrer;

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
 * @cache: A #EosCompanionAppServiceManagedCache which should e cleared when
 *         the installation state changes.
 * @cancellable: (nullable): A #GCancellable
 * @callback: A #GAsyncReadyCallback
 *
 * Asynchronously query for all available content applications installed
 * on the system, by examining all search providers and pulling information
 * out of desktop files.
 */
void eos_companion_app_service_list_application_infos (EosCompanionAppServiceManagedCache *cache,
                                                       GCancellable                       *cancellable,
                                                       GAsyncReadyCallback                 callback,
                                                       gpointer                            user_data);

/**
 * eos_companion_app_service_finish_list_application_infos:
 * @result: A #GAsyncResult
 * @error: A #GErrror
 *
 * Complete the call to eos_companion_app_service_list_application_infos by returning
 * a pointer array of #GDesktopAppInfo with entries from the application's .desktop file.
 *
 *
 * XXX: For some very strange reason, transferring the container to PyGI causes
 * it to immediately crash since it tries to unref the container straight away,
 * even though g_task_propagate_pointer is meant to be transfer full. Leak it
 * for now.
 *
 * Returns: (transfer none) (element-type EosCompanionAppServiceAppInfo): a #GPtrArray
            of #EosCompanionAppServiceAppInfo
 */
GPtrArray * eos_companion_app_service_finish_list_application_infos (GAsyncResult  *result,
                                                                     GError       **error);


/**
 * eos_companion_app_service_load_application_icon_data_async:
 * @icon_name: The name of the icon
 * @cancellable: (nullable): A #GCancellable
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



/**
 * eos_companion_app_service_load_application_info:
 * @name: The name of the application to load info for
 * @cache: A #EosCompanionAppServiceManagedCache used to cache flatpak info
 * @cancellable: (nullable): A #GCancellable
 * @callback: A #GAsyncReadyCallback
 * @user_data: Closure for @callback
 *
 * Asynchronously load application info for the given application name, passing
 * it as a #EosCompanionAppServiceAppInfo to the provided @callback
 */
void eos_companion_app_service_load_application_info (const gchar                        *name,
                                                      EosCompanionAppServiceManagedCache *cache,
                                                      GCancellable                       *cancellable,
                                                      GAsyncReadyCallback                 callback,
                                                      gpointer                            user_data);


/**
 * eos_companion_app_service_finish_load_application_info:
 * @result: A #GAsyncResult
 * @error: A #GError
 *
 * Complete the call to eos_companion_app_service_load_application_info by
 * returning a #EosCompanionAppServiceAppInfo containing the application's desktop data.
 *
 * Returns: (transfer none): a #EosCompanionAppServiceAppInfo containing application desktop data
 *                           or NULL if the desktop file did not exist.
 */
EosCompanionAppServiceAppInfo * eos_companion_app_service_finish_load_application_info (GAsyncResult  *result,
                                                                                        GError       **error);


/**
 * eos_companion_app_service_load_application_colors:
 * @app_id: The app ID of the application to load colors for
 * @cancellable: (nullable): A #GCancellable
 * @callback: A #GAsyncReadyCallback
 * @user_data: Closure for @callback
 *
 * Asynchronously load the application colors from the application's
 * internal reosurce file for the given application name,
 * passing back a GStrv to the provided @callback.
 */
void eos_companion_app_service_load_application_colors (const gchar         *app_id,
                                                        GCancellable        *cancellable,
                                                        GAsyncReadyCallback  callback,
                                                        gpointer             user_data);

/**
 * eos_companion_app_service_finish_load_application_colors:
 * @result: A #GAsyncResult
 * @error: A #GError
 *
 * Complete the call to eos_companion_app_service_load_application_colors
 * and return a #GStrv with the application colors in web-format.
 *
 * Returns: (transfer full): A #GStrv with the application colors
 */
GStrv eos_companion_app_service_finish_load_application_colors (GAsyncResult  *result,
                                                                GError       **error);

/**
 * eos_companion_app_service_load_all_in_stream_to_bytes:
 * @stream: A #GInputStream
 * @chunk_size: The chunk size to use in bytes when loading the stream.
 *              Higher chunk sizes will result in greater thoroughput due
 *              to less overhead, but will also consume greater amounts
 *              of memory. The final buffer size will always be truncated to
 *              the size of the read data.
 * @cancellable: (nullable): A #GCancellable
 * @callback: A #GAsyncReadyCallback
 * @callback_data: Closure for @callback
 *
 * Asynchronously read the entire stream into a #GBytes object, passed
 * to the provided @callback.
 *
 * Need this because EosShard uses GConverterInputStream and we can't measure
 * the size of the stream beforehand such that we could convert it to bytes.
 *
 * Use eos_companion_app_service_finish_load_all_in_stream_to_bytes
 * to complete the operation.
 */
void eos_companion_app_service_load_all_in_stream_to_bytes (GInputStream        *stream,
                                                            gsize                chunk_size,
                                                            GCancellable        *cancellable,
                                                            GAsyncReadyCallback  callback,
                                                            gpointer             callback_data);

/**
 * eos_companion_app_service_finish_load_all_in_stream_to_bytes:
 * @result: A #GAsyncResult
 * @error: A #GError
 *
 * Complete the call to eos_companion_app_service_load_all_in_stream_to_bytes
 * by returning the read #GBytes.
 *
 * Returns: (transfer none): a #GBytes
 */
GBytes * eos_companion_app_service_finish_load_all_in_stream_to_bytes (GAsyncResult  *result,
                                                                       GError       **error);

/**
 * eos_companion_app_service_bytes_to_string:
 * @bytes: A #GBytes
 *
 * Convert a #GBytes to a string. The string will be copied and a NUL-terminator
 * added to the end of it.
 *
 * Returns: (transfer none): A string.
 */
gchar * eos_companion_app_service_bytes_to_string (GBytes *bytes);


/**
 * eos_companion_app_service_string_to_bytes:
 * @string: (transfer none): A utf-8 string.
 *
 * Copy contents of string into a #Gbytes and return it.
 *
 * Returns: (transfer full): A string.
 */
GBytes * eos_companion_app_service_string_to_bytes (const gchar *string);

/**
 * eos_companion_app_service_get_runtime_spec_for_app_id:
 * @app_id: (transfer none): A utf-8 string.
 * @cache: An #EosCompanionAppServiceManagedCache.
 *
 * Blocking or cached fetch of the runtime spec for app id
 *
 * Returns: (transfer full): A string.
 */
gchar * eos_companion_app_service_get_runtime_spec_for_app_id (const gchar                         *app_id,
                                                               EosCompanionAppServiceManagedCache  *cache,
                                                               GError                             **error);

/**
 * eos_companion_app_service_fast_skip_stream_async
 * @stream: (transfer none): An #GInputStream to seek
 * @offset: offset in bytes to seek to
 * @cancellable: (nullable): A #GCancellable
 * @callback: A callback that will be invoked on success or failure once
 *            seeking is complete.
 * @user_data: The closure for @callback
 *
 * A wrapper around g_input_stream_skip that runs in a separate thread. The
 * default implementation of g_input_stream_skip_async, which EosShardBlob
 * uses will always attempt to read the entire stream up until a point in
 * a separate thread, whereas the synchronous version, g_input_stream_skip will
 * use the underlying GSeekable if it is available. Since the stream could
 * be compressed, we don't really know if it is skippable in O(1), so we need
 * to use g_input_stream_skip to account for the fact that we might have
 * to do it in the background to avoid blocking the main thread. And obviously,
 * we want to use the underlying GSeekable if it is available, hence having
 * to wrap g_input_stream_skip as opposed to using g_input_stream_skip_async
 * directly.
 */
void eos_companion_app_service_fast_skip_stream_async (GInputStream        *stream,
                                                       goffset              offset,
                                                       GCancellable        *cancellable,
                                                       GAsyncReadyCallback  callback,
                                                       gpointer             user_data);

/**
 * eos_companion_app_service_finish_fast_skip_stream
 * @result: A #GAsyncResult
 * @error: A #GError
 *
 * Complete the call to eos_companion_app_service_get_stream_at_offset_for_blob
 * by returning the newly seeked #GInputStream.
 *
 * Returns: (transfer none): a #GInputStream seeked to a given offset
 */
GInputStream * eos_companion_app_service_finish_fast_skip_stream (GAsyncResult  *result,
                                                                  GError       **error);

/**
 * eos_companion_app_service_flatpak_install_dirs
 *
 * List the directories where flatpaks are installed on the system. There
 * may be more than one, as is the case on split systems. These directories
 * may also be overridden by tests in the future.
 *
 * Note that this function may depend on the pointer-value of
 * EOS_COMPANION_APP_FLATPAK_SYSTEM_DIR and EOS_COMPANION_APP_FLATPAK_USER_DIR
 * - it is a programmer error to change those values whilst iterating over these
 * directories, even in another thread.
 *
 * Returns: (transfer none): a #GStrv of Flatpak install directories.
 */
GStrv eos_companion_app_service_flatpak_install_dirs (void);

G_END_DECLS

