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

#include <glib.h>
#include <gio/gdesktopappinfo.h>

#include <eknc-utils.h>

#include "eos-companion-app-integration-helper.h"
#include "eos-companion-app-integration-app-info.h"

#include <string.h>

/* To avoid having to include systemd in the runtime, we can just
 * listen for socket activation file descriptors starting from
 * what systemed wants to pass to us, which is fd 3 */
#define SYSTEMD_SOCKET_ACTIVATION_LISTEN_FDS_START 3

#define SUPPORTED_RUNTIME_NAME "com.endlessm.apps.Platform"
#define SUPPORTED_RUNTIME_BRANCH "2"

GQuark
eos_companion_app_service_error (void)
{
  return g_quark_from_static_string ("eos-companion-app-error");
}


/**
 * eos_companion_app_service_add_avahi_service_to_entry_group:
 * @group: An #GaEntryGroup
 * @name: The name of the service to add.
 * @type: The type of the service to add.
 * @domain: (nullable): The domain name for the service.
 * @host: (nullable): The host name for the service.
 * @port: The port name for the service.
 * @text: Entry for the TXT records
 *
 * We need this wrapper method since ga_entry_group_add_service_full uses
 * varargs and is not introspectable. Avahi provides a bindable
 * version called avahi_entry_group_add_service_strlist to provide a
 * string aray of TXT data but this is not wrapped by avahi-glib.
 *
 * XXX: Seems that we can't return the service directly without hitting
 * introspection errors.
 *
 * https://github.com/lathiat/avahi/issues/157
 *
 * Returns: TRUE if adding the service to the entry group succeeded, FALSE
 * with @error set otherwise
 */
gboolean
eos_companion_app_service_add_avahi_service_to_entry_group (GaEntryGroup  *group,
                                                            const gchar   *name,
                                                            const gchar   *type,
                                                            const gchar   *domain,
                                                            const gchar   *host,
                                                            guint          port,
                                                            const gchar   *text,
                                                            GError        **error)
{
  /* This is not explicitly documented, but it seems as though
   * ga_entry_group_add_service_full is transfer none, since it
   * allocates but appears to transfer ownership to an internal hashtable, so
   * we do not need to free memory here. */
  const GaEntryGroupService *service = ga_entry_group_add_service_full (group,
                                                                        AVAHI_IF_UNSPEC,
                                                                        AVAHI_PROTO_UNSPEC,
                                                                        0,
                                                                        name,
                                                                        type,
                                                                        domain,
                                                                        host,
                                                                        port,
                                                                        error,
                                                                        text,
                                                                        NULL);

  return service != NULL;
}

/**
 * eos_companion_app_service_set_soup_message_response:
 * @message: An #SoupMessage.
 * @content_type: The MIME content type.
 * @response: The response body.
 *
 * We need this wrapper method because soup_message_set_response only
 * takes a byte buffer
 */
void
eos_companion_app_service_set_soup_message_response (SoupMessage  *message,
                                                     const gchar  *content_type,
                                                     const gchar  *response)
{
  soup_message_set_response (message,
                             content_type,
                             SOUP_MEMORY_COPY,
                             response,
                             strlen (response));
}

/**
 * eos_companion_app_service_set_soup_message_response_bytes:
 * @message: An #SoupMessage.
 * @content_type: The MIME content type.
 * @bytes: The response body, as a #GBytes.
 *
 * We need this wrapper method because soup_message_set_response only
 * takes a byte buffer
 */
void
eos_companion_app_service_set_soup_message_response_bytes (SoupMessage  *message,
                                                           const gchar  *content_type,
                                                           GBytes       *bytes)
{
  gsize size = 0;
  gconstpointer response_data = g_bytes_get_data (bytes, &size);

  soup_message_set_response (message,
                             content_type,
                             SOUP_MEMORY_COPY,
                             response_data,
                             size);
}

/**
 * eos_companion_app_service_set_soup_message_request:
 * @message: An #SoupMessage.
 * @content_type: The MIME content type.
 * @request: The request body.
 *
 * We need this wrapper method because soup_message_set_request only
 * takes a byte buffer
 */
void
eos_companion_app_service_set_soup_message_request (SoupMessage  *message,
                                                    const gchar  *content_type,
                                                    const gchar  *request)
{
  soup_message_set_request (message,
                            content_type,
                            SOUP_MEMORY_COPY,
                            request,
                            strlen (request));
}

/**
 * eos_companion_app_service_soup_server_listen_on_sd_fd_or_port:
 * @server: A #SoupServer.
 * @port: A port to listen on if an fd is not passed.
 * @options: #SoupServerListenOptions
 * @error: A #GError
 *
 * Start listening on either the file descriptor passed to us by systemd
 * or on a pre-defined port number.
 *
 * Returns: TRUE if the operation succeeded, FALSE with @error set on failure.
 */
gboolean
eos_companion_app_service_soup_server_listen_on_sd_fd_or_port (SoupServer               *server,
                                                               guint                     port,
                                                               SoupServerListenOptions   options,
                                                               GError                  **error)
{
  g_autoptr(GError) local_error = NULL;

  if (!soup_server_listen_fd (server,
                              SYSTEMD_SOCKET_ACTIVATION_LISTEN_FDS_START,
                              options,
                              &local_error))
    {
      /* We just get a generic failure if we try and listen on a bad socket,
       * so try to listen on the port instead if this happens */
      if (!g_error_matches (local_error, G_IO_ERROR, G_IO_ERROR_FAILED))
        {
          g_propagate_error (error, g_steal_pointer (&local_error));
          return FALSE;
        }

      return soup_server_listen_all (server, port, options, error);
    }

  return TRUE;
}

static inline gboolean
is_content_app_from_app_name (const gchar *app_name)
{
  const gchar *ptr = app_name;
  gsize ndot = 0;

  for (ptr = app_name; *ptr != '\0'; ++ptr)
    if (*ptr == '.')
      ++ndot;

  return ndot == 3;
}

/* Do not manipulate these directly */
static GMutex _supported_applications_cache_mutex;
static GHashTable *_supported_applications_cache = NULL;

/* Sets *is_supported to TRUE if the application was supported according
 * to the cache, and FALSE if it was not supported according to the cache.
 *
 * Returns TRUE on cache_hit and FALSE otherwise. */
static gboolean
application_is_supported_cache (const gchar *app_id, gboolean *is_supported)
{
  gboolean ret = FALSE;

  g_return_val_if_fail (is_supported != NULL, FALSE);
  g_mutex_lock (&_supported_applications_cache_mutex);

  if (_supported_applications_cache == NULL)
    _supported_applications_cache = g_hash_table_new (g_str_hash, g_str_equal);

  ret = g_hash_table_lookup_extended (_supported_applications_cache,
                                      app_id,
                                      NULL,
                                      (gpointer *) &is_supported);

  g_mutex_unlock (&_supported_applications_cache_mutex);
  return ret;
}

static gboolean
record_application_is_supported_cache (const gchar *app_id, gboolean is_supported)
{
  g_mutex_lock (&_supported_applications_cache_mutex);

  if (_supported_applications_cache == NULL)
    _supported_applications_cache = g_hash_table_new (g_str_hash, g_str_equal);

  g_hash_table_insert (_supported_applications_cache,
                       g_strdup (app_id),
                       GINT_TO_POINTER (is_supported));

  g_mutex_unlock (&_supported_applications_cache_mutex);
  return is_supported;
}

/* Check if the application will be supported by the companion app - right
 * now this should always return true, but we will need this check
 * to stick around once we remove the whitelist and expand support to
 * a wider range of applications. */
static gboolean
application_is_supported (const gchar *app_id)
{
  g_autoptr(GFile) data_dir = NULL;
  gboolean supported_cache = FALSE;

  if (application_is_supported_cache (app_id, &supported_cache))
    return supported_cache;

  data_dir = eknc_get_data_dir (app_id);
  return record_application_is_supported_cache (app_id, data_dir != NULL);
}

const gchar *supported_applications[] = {
  "com.endlessm.test_with_martin.en",
  "com.endlessm.celebrities.en",
  "com.endlessm.history.en",
  "com.endlessm.animals.en",
  "com.endlessm.astronomy.en",
  NULL
};

static GPtrArray *
list_application_infos (GCancellable  *cancellable,
                        GError       **error)
{
  const gchar **iter = supported_applications;
  g_autoptr(GPtrArray) app_infos = g_ptr_array_new_with_free_func (g_object_unref);

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *desktop_id = NULL;
      g_autoptr(GDesktopAppInfo) desktop_info = NULL;
      g_autoptr(EosCompanionAppServiceAppInfo) info = NULL;

      if (!application_is_supported (*iter))
        continue;

      /* XXX: This isn't great, but still needed to filter for apps that are
       * actually content apps */
      if (!is_content_app_from_app_name (*iter))
        continue;

      /* XXX: Again, also not great */
      desktop_id = g_strdup_printf ("%s.desktop", *iter);
      desktop_info = g_desktop_app_info_new (desktop_id);

      if (desktop_info == NULL)
        continue;

      info = eos_companion_app_service_app_info_new (*iter,
                                                     g_app_info_get_display_name (G_APP_INFO (desktop_info)));

      g_ptr_array_add (app_infos, g_steal_pointer (&info));
    }

  return g_steal_pointer (&app_infos);
}

GPtrArray *
eos_companion_app_service_finish_list_application_infos (GAsyncResult  *result,
                                                         GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

static void
list_application_infos_thread (GTask        *task,
                               gpointer      source,
                               gpointer      task_data,
                               GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  g_autoptr(GPtrArray) application_infos_array =
    list_application_infos (cancellable, &local_error);

  if (application_infos_array == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task,
                         g_steal_pointer (&application_infos_array),
                         (GDestroyNotify) g_ptr_array_unref);
}

void
eos_companion_app_service_list_application_infos (GCancellable        *cancellable,
                                                  GAsyncReadyCallback  callback,
                                                  gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, NULL);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_run_in_thread (task, list_application_infos_thread);
}


GBytes *
eos_companion_app_service_finish_load_application_icon_data_from_data_dirs (GAsyncResult  *result,
                                                                            GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

/* I'm still surprised the things which are not in Gio ... */
static GBytes *
read_file_into_memory (GFile         *file,
                       GCancellable  *cancellable,
                       GError       **error)
{
  g_autoptr(GFileInfo) finfo = NULL;
  g_autoptr(GFileInputStream) fstream = g_file_read (file,
                                                     cancellable,
                                                     error);
  goffset size = 0;

  if (fstream == NULL)
    return NULL;

  finfo = g_file_input_stream_query_info (fstream,
                                          G_FILE_ATTRIBUTE_STANDARD_SIZE,
                                          cancellable,
                                          error);

  if (finfo == NULL)
    return NULL;

  return g_input_stream_read_bytes (G_INPUT_STREAM (fstream),
                                    (gsize) g_file_info_get_size (finfo),
                                    cancellable,
                                    error);
}

static GBytes *
read_icon_from_data_dirs (const gchar   *icon_id,
                          GCancellable  *cancellable,
                          GError       **error)
{
  const gchar * const *data_dirs = g_get_system_data_dirs ();
  const gchar * const *iter = data_dirs;

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *basename = g_strdup_printf ("%s.png", icon_id);
      g_autofree gchar *expected_path = g_build_filename (*iter,
                                                          "icons",
                                                          "hicolor",
                                                          "64x64",
                                                          "apps",
                                                          basename,
                                                          NULL);
      g_autoptr(GError) local_error = NULL;
      g_autoptr(GFile) expected_icon_file = g_file_new_for_path (expected_path);
      g_autoptr(GBytes) bytes = read_file_into_memory (expected_icon_file,
                                                       cancellable,
                                                       &local_error);

      if (bytes == NULL)
        {
          if (!g_error_matches (local_error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND))
            {
              g_propagate_error (error, g_steal_pointer (&local_error));
              return NULL;
            }

          g_clear_error (&local_error);
          continue;
        }

      return g_steal_pointer (&bytes);
    }

  g_set_error (error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND, "No icon for %s found", icon_id);
  return NULL;
}

static void
load_application_icon_data_from_data_dirs_thread (GTask        *task,
                                                  gpointer      source,
                                                  gpointer      task_data,
                                                  GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  g_autoptr(GBytes) icon_bytes = read_icon_from_data_dirs ((const gchar *) task_data,
                                                           cancellable,
                                                           &local_error);

  if (icon_bytes == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task, g_steal_pointer (&icon_bytes), (GDestroyNotify) g_bytes_unref);
}

/* This kludge only exists because there doesn't appear to be a straightforward
 * way of getting pixmap data out of a GThemedIcon. */
void
eos_companion_app_service_load_application_icon_data_from_data_dirs (const gchar         *icon_name,
                                                                     GCancellable        *cancellable,
                                                                     GAsyncReadyCallback  callback,
                                                                     gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, NULL);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_set_task_data (task, g_strdup (icon_name), g_free);
  g_task_run_in_thread (task, load_application_icon_data_from_data_dirs_thread);
}

typedef struct _ReadBufferInfo
{
  GInputStream *stream;
  gpointer      data;
  gsize         chunk_size;
} ReadBufferInfo;

static ReadBufferInfo *
read_buffer_info_new (GInputStream *stream, gsize chunk_size)
{
  ReadBufferInfo *info = g_slice_new0 (ReadBufferInfo);
  info->stream = g_object_ref (stream);
  info->chunk_size = chunk_size;

  return info;
}

static void
read_buffer_info_free (ReadBufferInfo *info)
{
  g_clear_object (&info->stream);
  g_clear_pointer (&info->data, g_free);

  g_slice_free (ReadBufferInfo, info);
}

GBytes *
eos_companion_app_service_finish_load_all_in_stream_to_bytes (GAsyncResult  *result,
                                                              GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

static void
load_all_in_stream_to_bytes_thread_func (GTask        *task,
                                         gpointer      source,
                                         gpointer      task_data,
                                         GCancellable *cancellable)
{
  ReadBufferInfo *info = task_data;
  gsize allocated = 0;
  gsize read_bytes = 0;
  g_autofree gpointer buffer = NULL;

  /* If this is the case, we still have more work to do */
  while (allocated == read_bytes)
    {
      g_autoptr(GError) local_error = NULL;
      gsize bytes_read_on_this_iteration;
      allocated += info->chunk_size;
      buffer = g_realloc (buffer, allocated * sizeof (gchar));

      if (!g_input_stream_read_all (info->stream,
                                    ((gchar *) buffer + read_bytes),
                                    info->chunk_size,
                                    &bytes_read_on_this_iteration,
                                    cancellable,
                                    &local_error))
        {
          g_message ("Return error %s", local_error->message);
          g_task_return_error (task, g_steal_pointer (&local_error));
          return;
        }

      /* Otherwise, add the number of bytes read to our running total
       * and go around. If we read fewer bytes than allocated, then
       * we're done */
      read_bytes += bytes_read_on_this_iteration;
    }

  /* Truncate, store as bytes and transfer to task */
  buffer = g_realloc (buffer, read_bytes * sizeof (gchar));
  g_task_return_pointer (task,
                         g_bytes_new_take (g_steal_pointer (&buffer),
                                           read_bytes),
                         (GDestroyNotify) g_bytes_unref);
}

void
eos_companion_app_service_load_all_in_stream_to_bytes (GInputStream        *stream,
                                                       gsize                chunk_size,
                                                       GCancellable        *cancellable,
                                                       GAsyncReadyCallback  callback,
                                                       gpointer             callback_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, callback_data);

  g_task_set_task_data (task,
                        read_buffer_info_new (stream, chunk_size),
                        (GDestroyNotify) read_buffer_info_free);
  g_task_run_in_thread (task, load_all_in_stream_to_bytes_thread_func);
}


G_DEFINE_QUARK (eos-companion-app-service-error-quark, eos_companion_app_service_error)

