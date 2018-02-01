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

#include <errno.h>
#include <string.h>
#include <sys/prctl.h>

#include <gdk-pixbuf/gdk-pixbuf.h>
#include <glib.h>
#include <gio/gdesktopappinfo.h>
#include <gtk/gtk.h>

#include <eknc-utils.h>

#include "eos-companion-app-integration-helper.h"

#include <string.h>

/* To avoid having to include systemd in the runtime, we can just
 * listen for socket activation file descriptors starting from
 * what systemed wants to pass to us, which is fd 3 */
#define SYSTEMD_SOCKET_ACTIVATION_LISTEN_FDS_START 3

#define SUPPORTED_RUNTIME_NAME "com.endlessm.apps.Platform"
#define SUPPORTED_RUNTIME_BRANCH "3"

GQuark
eos_companion_app_service_error (void)
{
  return g_quark_from_static_string ("eos-companion-app-error");
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

  g_message ("Trying to listen on file descriptor 3");
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

      g_message ("Failed to listen on FD 3. Listening on port 1110 instead");
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
                                      (gpointer *) is_supported);

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

static gboolean
parse_runtime_spec (const gchar  *runtime_spec,
                    gchar       **out_runtime_name,
                    gchar       **out_runtime_version,
                    GError      **error)
{
  g_autoptr(GRegex) regex = NULL;
  g_autoptr(GMatchInfo) info = NULL;

  g_return_val_if_fail (out_runtime_name != NULL, FALSE);
  g_return_val_if_fail (out_runtime_version != NULL, FALSE);

  regex = g_regex_new ("(.*?)\\/.*?\\/(.*)", 0, 0, error);

  if (regex == NULL)
    return FALSE;

  if (!g_regex_match (regex, runtime_spec, 0, &info))
    {
      g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED, "Failed parse %s", runtime_spec);
      return FALSE;
    }

  *out_runtime_name = g_match_info_fetch (info, 1);
  *out_runtime_version = g_match_info_fetch (info, 2);

  return TRUE;
}

static gboolean
app_is_compatible (const gchar  *app_id,
                   const gchar  *runtime_spec,
                   gboolean     *out_app_is_compatible,
                   GError      **error)
{
  g_autoptr(GFile) data_dir = NULL;
  gboolean supported_cache = FALSE;
  gchar *runtime_name = NULL;
  gchar *arch = NULL;
  gchar *runtime_version = NULL;

  if (application_is_supported_cache (app_id, &supported_cache))
    {
      *out_app_is_compatible = supported_cache;
      return TRUE;
    }

  if (!parse_runtime_spec (runtime_spec, &runtime_name, &runtime_version, error))
    return FALSE;

  if (g_strcmp0 (runtime_name, SUPPORTED_RUNTIME_NAME) != 0)
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, FALSE);
      return TRUE;
    }

  if (g_strcmp0 (runtime_version, SUPPORTED_RUNTIME_BRANCH) != 0)
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, FALSE);
      return TRUE;
    }

  if (!is_content_app_from_app_name (app_id))
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, FALSE);
      return TRUE;
    }

  data_dir = eknc_get_data_dir (app_id);
  *out_app_is_compatible = record_application_is_supported_cache (app_id, data_dir != NULL);
  return TRUE;
}

static gboolean
examine_flatpak_metadata (const gchar  *flatpak_directory,
                          gchar       **out_app_name,
                          gchar       **out_runtime_spec,
                          GError      **error)
{
  g_autoptr(GKeyFile) keyfile = NULL;
  g_autofree gchar *metadata_path = NULL;
  g_autofree gchar *app_name = NULL;
  g_autofree gchar *runtime_spec = NULL;

  g_return_val_if_fail (out_app_name != NULL, FALSE);
  g_return_val_if_fail (out_runtime_spec != NULL, FALSE);

  metadata_path = g_build_filename (flatpak_directory,
                                    "current",
                                    "active",
                                    "metadata",
                                    NULL);
  keyfile = g_key_file_new ();

  if (!g_key_file_load_from_file (keyfile, metadata_path, G_KEY_FILE_NONE, error))
    return FALSE;

  app_name = g_key_file_get_string (keyfile, "Application", "name", error);

  if (!app_name)
    return FALSE;

  runtime_spec = g_key_file_get_string (keyfile, "Application", "runtime", error);

  if (!runtime_spec)
    return FALSE;

  *out_app_name = g_steal_pointer (&app_name);
  *out_runtime_spec = g_steal_pointer (&runtime_spec);

  return TRUE;
}

gchar *
eos_companion_app_service_get_runtime_name_for_app_id (const gchar  *app_id,
                                                       GError      **error)
{
  g_autofree gchar *flatpak_directory = g_build_filename ("/",
                                                          "var",
                                                          "lib",
                                                          "flatpak",
                                                          "app",
                                                          app_id,
                                                          NULL);
  g_autofree gchar *app_name = NULL;
  g_autofree gchar *runtime_name = NULL;

  if (!examine_flatpak_metadata (flatpak_directory, &app_name, &runtime_name, error))
    return FALSE;

  return g_steal_pointer (&runtime_name);
}

static const gchar *flatpak_applications_directory_path = "/var/lib/flatpak/app";

/* This function is required in order to be able to create a GDesktopAppInfo
 * out of Desktop Entry Key File within the Flatpak sandbox. We cannot use
 * g_desktop_app_info_new or g_desktop_app_info_new_from_keyfile directly,
 * since GIO will examine the Exec= line and and notice that /usr/bin/flatpak
 * does not exist. Obviously we cannot make it exist inside the sandbox since
 * it is not possible to mount /usr. nor would want want to vendor-bundle
 * flatpak for this purpose.
 *
 * Since we'll never actually be launching the application (this runs as
 * a system-level service), set the "Exec=" line to /bin/true so that
 * the binary-check always succeeds and we can continue to use the
 * GDesktopAppInfo interface for reading the keyfile.
 */
static GDesktopAppInfo *
key_file_to_desktop_app_info_in_sandbox (GKeyFile *key_file)
{
  g_key_file_set_string (key_file, "Desktop Entry", "Exec", "/bin/true");
  return g_desktop_app_info_new_from_keyfile (key_file);
}

/* Try and load directly from the flatpak directory first, if that fails,
 * fallback to using GDesktopAppInfo and loading from that (in case an
 * app was installed systemwide) */
static gboolean
load_desktop_info_key_file_for_app_id (const gchar      *app_id,
                                       GDesktopAppInfo **out_app_info,
                                       GError          **error)
{
  g_autofree gchar *desktop_id = NULL;
  g_autofree gchar *flatpak_desktop_file_path = NULL;
  g_autoptr(GDesktopAppInfo) desktop_info = NULL;
  g_autoptr(GKeyFile) key_file = NULL;
  g_autoptr(GError) local_error = NULL;

  g_return_val_if_fail (out_app_info != NULL, FALSE);

  desktop_id = g_strdup_printf ("%s.desktop", app_id);
  flatpak_desktop_file_path = g_build_filename ("/",
                                                "var",
                                                "lib",
                                                "flatpak",
                                                "exports",
                                                "share",
                                                "applications",
                                                desktop_id,
                                                NULL);
  key_file = g_key_file_new ();

  if (!g_key_file_load_from_file (key_file,
                                  flatpak_desktop_file_path,
                                  G_KEY_FILE_NONE,
                                  &local_error))
    {
      if (!g_error_matches (local_error, G_FILE_ERROR, G_FILE_ERROR_NOENT))
        {
          g_propagate_error (error, g_steal_pointer (&local_error));
          return FALSE;
        }

      g_clear_error (&local_error);

      *out_app_info = g_desktop_app_info_new (desktop_id);

      /* This function only returns FALSE on error and not finding the
       * GDesktopAppInfo here using g_desktop_app_info_new is not
       * an error. Return TRUE now. */
      return TRUE;
    }

  *out_app_info = key_file_to_desktop_app_info_in_sandbox (key_file);
  return TRUE;
}

static GPtrArray *
list_application_infos (GCancellable  *cancellable,
                        GError       **error)
{
  g_autoptr(GFile) flatpak_applications_directory = g_file_new_for_path (flatpak_applications_directory_path);
  g_autoptr(GFileEnumerator) enumerator = g_file_enumerate_children (flatpak_applications_directory,
                                                                     G_FILE_ATTRIBUTE_STANDARD_NAME,
                                                                     G_FILE_QUERY_INFO_NONE,
                                                                     cancellable,
                                                                     error);
  g_autoptr(GPtrArray) app_infos = NULL;

  if (enumerator == NULL)
    return NULL;

  app_infos = g_ptr_array_new_with_free_func (g_object_unref);

  while (TRUE)
    {
      GFile *child = NULL;
      GFileInfo *info = NULL;
      g_autofree gchar *flatpak_directory = NULL;
      g_autofree gchar *runtime_name = NULL;
      g_autofree gchar *app_name = NULL;
      g_autoptr(GDesktopAppInfo) app_info = NULL;
      gboolean is_compatible_app = FALSE;

      if (!g_file_enumerator_iterate (enumerator, &info, &child, cancellable, error))
        return NULL;

      if (!info)
        break;

      flatpak_directory = g_build_filename (flatpak_applications_directory_path,
                                            g_file_info_get_name (info),
                                            NULL);

      /* Look inside the metadata for each flatpak to work out what runtime
       * it is using */
      if (!examine_flatpak_metadata (flatpak_directory, &app_name, &runtime_name, error))
        return NULL;

      /* Check if the application is an eligible content app */
      if (!app_is_compatible (app_name, runtime_name, &is_compatible_app, error))
        return NULL;

      if (!is_compatible_app)
        continue;

      if (!load_desktop_info_key_file_for_app_id (app_name, &app_info, error))
        return NULL;

      /* If nothing loaded, this app is not compatible, continue */
      if (app_info == NULL)
        continue;

      g_ptr_array_add (app_infos, g_steal_pointer (&app_info));
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
eos_companion_app_service_finish_load_application_icon_data_async (GAsyncResult  *result,
                                                                   GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

static void
load_application_info_thread (GTask        *task,
                              gpointer      source,
                              gpointer      task_data,
                              GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  g_autoptr(GDesktopAppInfo) app_info = NULL;

  if (!load_desktop_info_key_file_for_app_id ((const gchar *) task_data,
                                              &app_info,
                                              &local_error))
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task,
                         g_steal_pointer (&app_info),
                         (GDestroyNotify) g_object_unref);
}

void
eos_companion_app_service_load_application_info (const gchar         *name,
                                                 GCancellable        *cancellable,
                                                 GAsyncReadyCallback  callback,
                                                 gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_set_task_data (task, g_strdup (name), g_free);
  g_task_run_in_thread (task, load_application_info_thread);
}

GDesktopAppInfo *
eos_companion_app_service_finish_load_application_info (GAsyncResult  *result,
                                                        GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

/* Returns a GtkIconTheme * object, unique to this program.
 *
 * We have to do this instead of using gtk_icon_theme_get_default(), since
 * the latter depends on a GdkScreen, and thus an X connection, which we
 * do not have. */
static GtkIconTheme *
get_singleton_icon_theme ()
{
  static gsize initialization_value = 0;
  static GtkIconTheme *theme = NULL;

  if (g_once_init_enter (&initialization_value))
    {
      g_autofree gchar *icons_path = g_build_filename ("/",
                                                       "var",
                                                       "lib",
                                                       "flatpak",
                                                       "exports",
                                                       "share",
                                                       "icons",
                                                       NULL);
      theme = gtk_icon_theme_new ();
      gtk_icon_theme_prepend_search_path (theme, icons_path);
      g_once_init_leave (&initialization_value, 1);
    }

  return theme;
}

static GBytes *
read_icon_pixbuf_png_bytes_for_name (const gchar   *icon_id,
                                     GCancellable  *cancellable,
                                     GError       **error)
{
  g_autofree gchar *buffer = NULL;
  gsize buffer_size = 0;
  g_autoptr(GdkPixbuf) pixbuf = gtk_icon_theme_load_icon (get_singleton_icon_theme (),
                                                          icon_id,
                                                          64,
                                                          0,
                                                          error);

  if (pixbuf == NULL)
    return NULL;

  if (!gdk_pixbuf_save_to_buffer (pixbuf, &buffer, &buffer_size, "png", error, NULL))
    return NULL;

  return g_bytes_new_take (g_steal_pointer (&buffer), buffer_size);
}

static void
load_application_icon_data_thread (GTask        *task,
                                   gpointer      source,
                                   gpointer      task_data,
                                   GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  g_autoptr(GBytes) icon_bytes = read_icon_pixbuf_png_bytes_for_name ((const gchar *) task_data,
                                                                      cancellable,
                                                                      &local_error);

  if (icon_bytes == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task, g_steal_pointer (&icon_bytes), (GDestroyNotify) g_bytes_unref);
}

/* We'll do this to avoid blocking the main thread on loading image data */
void
eos_companion_app_service_load_application_icon_data_async (const gchar         *icon_name,
                                                            GCancellable        *cancellable,
                                                            GAsyncReadyCallback  callback,
                                                            gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_set_task_data (task, g_strdup (icon_name), g_free);
  g_task_run_in_thread (task, load_application_icon_data_thread);
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

/* It'd be nice if there was a way to do this without copying the underlying
 * data */
gchar *
eos_companion_app_service_bytes_to_string (GBytes *bytes)
{
  gsize length;
  const gchar *str = g_bytes_get_data (bytes, &length);
  gchar *buffer = g_malloc ((length + 1) * sizeof (gchar));

  memcpy ((gpointer) buffer, (gconstpointer) str, length * sizeof (gchar));
  buffer[length] = '\0';

  return buffer;
}

GBytes *
eos_companion_app_service_string_to_bytes (const gchar *string)
{
  return g_bytes_new (string, strlen (string));
}

typedef struct _FastSeekData
{
  GInputStream *stream;
  goffset       seek_point;
} FastSeekData;

static FastSeekData *
fast_seek_data_new (GInputStream *stream,
                    goffset       seek_point)
{
  FastSeekData *data = g_slice_new0 (FastSeekData);

  data->stream = g_object_ref (stream);
  data->seek_point = seek_point;

  return data;
}

static void
fast_seek_data_free (FastSeekData *data)
{
  g_clear_object (&data->stream);

  g_slice_free (FastSeekData, data);
}

static void
get_stream_offset_thread_func (GTask        *task,
                               gpointer      source,
                               gpointer      task_data,
                               GCancellable *cancellable)
{
  FastSeekData *data = task_data;
  GInputStream *stream = data->stream;
  g_autoptr(GError) local_error = NULL;

  /* Depending on whether or not the stream is seekable, this will be done
   * in either O(1) or O(N) */
  if (g_input_stream_skip (stream,
                           data->seek_point,
                           cancellable,
                           &local_error) == -1)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  /* Return the newly seeked stream back to the main thread */
  g_task_return_pointer (task, stream, g_object_unref);
}

void
eos_companion_app_service_fast_skip_stream_async (GInputStream        *stream,
                                                  goffset              offset,
                                                  GCancellable        *cancellable,
                                                  GAsyncReadyCallback  callback,
                                                  gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);
  g_task_set_task_data (task,
                        fast_seek_data_new (stream, offset),
                        (GDestroyNotify) fast_seek_data_free);
  g_task_run_in_thread (task, get_stream_offset_thread_func);
}

GInputStream *
eos_companion_app_service_finish_fast_skip_stream (GAsyncResult  *result,
                                                   GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (G_TASK (result), NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

gboolean
eos_companion_app_service_set_traceable (GError **error)
{
  g_return_val_if_fail (error != NULL, FALSE);

  if (prctl (PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0) == -1)
    {
      g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED, strerror (errno));
      return FALSE;
    }

  return TRUE;
}

G_DEFINE_QUARK (eos-companion-app-service-error-quark, eos_companion_app_service_error)

