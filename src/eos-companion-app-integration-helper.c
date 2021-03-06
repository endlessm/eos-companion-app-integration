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

#include <gdk-pixbuf/gdk-pixbuf.h>
#include <glib.h>
#include <gio/gdesktopappinfo.h>
#include <gtk/gtk.h>

#include "config.h"
#include "eos-companion-app-service-app-info.h"
#include "eos-companion-app-service-managed-cache-private.h"
#include "eos-companion-app-integration-helper.h"

#include <string.h>

/* To avoid having to include systemd in the runtime, we can just
 * listen for socket activation file descriptors starting from
 * what systemed wants to pass to us, which is fd 3 */
#define SYSTEMD_SOCKET_ACTIVATION_LISTEN_FDS_START 3

#define SUPPORTED_RUNTIME_NAME "com.endlessm.apps.Platform"

/* Needed to get autocleanups of GResource files */
G_DEFINE_AUTOPTR_CLEANUP_FUNC (GResource, g_resource_unref)

GQuark
eos_companion_app_service_error (void)
{
  return g_quark_from_static_string ("eos-companion-app-service-error");
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
  const char *started_by_systemd = g_getenv ("EOS_COMPANION_APP_SERVICE_STARTED_BY_SYSTEMD");

  if (started_by_systemd != NULL)
    return soup_server_listen_fd (server, SYSTEMD_SOCKET_ACTIVATION_LISTEN_FDS_START,
                                  options, error);

  /* Not started by systemd, listen on port */
  return soup_server_listen_all (server, port, options, error);
}

static gboolean
is_content_app (const gchar *app_id)
{
  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *path = g_build_filename (*iter,
                                                 "app",
                                                 app_id,
                                                 "current",
                                                 "active",
                                                 "files",
                                                 "share",
                                                 "ekn",
                                                 "data",
                                                 app_id,
                                                 NULL);

      if (g_file_test (path, G_FILE_TEST_EXISTS))
        return TRUE;
    }

  return FALSE;
}

#define APP_SUPPORTED_KEY "application-id-supported"

/* Sets *is_supported to TRUE if the application was supported according
 * to the cache, and FALSE if it was not supported according to the cache.
 *
 * Returns TRUE on cache_hit and FALSE otherwise. */
static gboolean
application_is_supported_cache (const gchar                        *app_id,
                                EosCompanionAppServiceManagedCache *cache,
                                gboolean                           *is_supported)
{
  GHashTable *supported_cache = NULL;
  gpointer value = NULL;
  gboolean ret;

  g_return_val_if_fail (is_supported != NULL, FALSE);

  supported_cache =
    eos_companion_app_service_managed_cache_lock_subcache (cache, APP_SUPPORTED_KEY, NULL);

  *is_supported = GPOINTER_TO_INT (g_hash_table_lookup (supported_cache, app_id));

  eos_companion_app_service_managed_cache_unlock_subcache (cache, APP_SUPPORTED_KEY);
}

static gboolean
record_application_is_supported_cache (const gchar                        *app_id,
                                       EosCompanionAppServiceManagedCache *cache,
                                       gboolean                            is_supported)
{
  GHashTable *supported_cache =
    eos_companion_app_service_managed_cache_lock_subcache (cache, APP_SUPPORTED_KEY, NULL);

  g_hash_table_insert (supported_cache, g_strdup (app_id), GINT_TO_POINTER (is_supported));

  eos_companion_app_service_managed_cache_unlock_subcache (cache, APP_SUPPORTED_KEY);
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

  regex = g_regex_new ("(.*?)\\/.*?\\/(.*)", 0, 0, error);

  if (regex == NULL)
    return FALSE;

  if (!g_regex_match (regex, runtime_spec, 0, &info))
    {
      g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED, "Failed parse %s", runtime_spec);
      return FALSE;
    }

  if (out_runtime_name != NULL)
    *out_runtime_name = g_match_info_fetch (info, 1);

  if (out_runtime_version != NULL)
    *out_runtime_version = g_match_info_fetch (info, 2);

  return TRUE;
}

static gboolean
runtime_version_is_supported (const gchar *runtime_version)
{
  static const gchar *supported_runtime_versions[] = {
    "1",
    "2",
    "3",
    "4",
    "5",
    NULL
  };

  return g_strv_contains (supported_runtime_versions, runtime_version);
}

static gboolean
app_is_compatible (const gchar                         *app_id,
                   const gchar                         *runtime_name,
                   const gchar                         *runtime_version,
                   EosCompanionAppServiceManagedCache  *cache,
                   gboolean                            *out_app_is_compatible,
                   GError                             **error)
{
  gboolean supported_cache = FALSE;

  if (application_is_supported_cache (app_id, cache, &supported_cache))
    {
      *out_app_is_compatible = supported_cache;
      return TRUE;
    }

  if (g_strcmp0 (runtime_name, SUPPORTED_RUNTIME_NAME) != 0)
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, cache, FALSE);
      return TRUE;
    }

  if (!runtime_version_is_supported (runtime_version))
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, cache, FALSE);
      return TRUE;
    }

  if (!is_content_app (app_id))
    {
      *out_app_is_compatible = record_application_is_supported_cache (app_id, cache, FALSE);
      return TRUE;
    }

  *out_app_is_compatible = record_application_is_supported_cache (app_id, cache, TRUE);
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

static gchar *
blocking_get_runtime_spec_for_app_id (const gchar  *app_id,
                                      GError      **error)
{
  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *flatpak_directory = g_build_filename (*iter,
                                                              "app",
                                                              app_id,
                                                              NULL);
      g_autofree gchar *app_name = NULL;
      g_autofree gchar *runtime_spec = NULL;
      g_autoptr(GError) local_error = NULL;

      if (!examine_flatpak_metadata (flatpak_directory, &app_name, &runtime_spec, &local_error))
        {
          /* App doesn't exist at that directory, try the other one */
          if (g_error_matches (local_error, G_FILE_ERROR, G_FILE_ERROR_NOENT))
            {
              g_clear_error (&local_error);
              continue;
            }

          g_propagate_error (error, g_steal_pointer (&local_error));
          return NULL;
        }

      return g_steal_pointer (&runtime_spec);
    }

  /* Not found in either, return INVALID_APP_ID */
  g_set_error (error,
               EOS_COMPANION_APP_SERVICE_ERROR,
               EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID,
               "Application %s is not installed",
               app_id);
  return NULL;
}

#define RUNTIME_SPEC_KEY_NAME "runtime-spec"

gchar *
eos_companion_app_service_get_runtime_spec_for_app_id (const gchar                         *app_id,
                                                       EosCompanionAppServiceManagedCache  *cache,
                                                       GError                             **error)
{
  GHashTable *subcache =
    eos_companion_app_service_managed_cache_lock_subcache (cache,
                                                           RUNTIME_SPEC_KEY_NAME,
                                                           g_free);
  const gchar *runtime_spec_value = NULL;

  if ((runtime_spec_value = g_hash_table_lookup (subcache, app_id)) == NULL)
    {
      gchar *runtime_spec = blocking_get_runtime_spec_for_app_id (app_id, error);

      if (runtime_spec == NULL)
        {
          eos_companion_app_service_managed_cache_unlock_subcache (cache,
                                                                   RUNTIME_SPEC_KEY_NAME);
          return NULL;
        }

      /* Transfer the runtime_spec to the registered cache */
      g_hash_table_insert (subcache, g_strdup (app_id), runtime_spec);
      runtime_spec_value = runtime_spec;
    }

  eos_companion_app_service_managed_cache_unlock_subcache (cache,
                                                           RUNTIME_SPEC_KEY_NAME);
  return g_strdup (runtime_spec_value);
}

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

/* Try and load directly from the flatpak directories first, if that fails,
 * fallback to using GDesktopAppInfo and loading from that (in case an
 * app was installed systemwide) */
static GDesktopAppInfo *
load_desktop_info_key_file_for_app_id (const gchar      *app_id,
                                       GError          **error)
{
  g_autofree gchar *desktop_id = g_strdup_printf ("%s.desktop", app_id);
  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();
  g_autoptr(GDesktopAppInfo) system_desktop_app_info = NULL;

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *flatpak_desktop_file_path = g_build_filename (*iter,
                                                                      "exports",
                                                                      "share",
                                                                      "applications",
                                                                      desktop_id,
                                                                      NULL);
      g_autoptr(GKeyFile) key_file = g_key_file_new ();
      g_autoptr(GError) local_error = NULL;

      if (!g_key_file_load_from_file (key_file,
                                      flatpak_desktop_file_path,
                                      G_KEY_FILE_NONE,
                                      &local_error))
        {
          if (!g_error_matches (local_error, G_FILE_ERROR, G_FILE_ERROR_NOENT))
            {
              g_propagate_error (error, g_steal_pointer (&local_error));
              return NULL;
            }

          g_clear_error (&local_error);
          continue;
        }

      return key_file_to_desktop_app_info_in_sandbox (key_file);
    }

  /* We used to call g_desktop_app_info_new here as a fallback
   * to try and find the .desktop file in the system directories,
   * however that is a mostly pointless exercise considering that
   * all content apps are going to be installed as flatpaks and
   * there's no chance that the .desktop file is going to
   * be in the system data dirs on the flatpak runtime. Additionally,
   * since this code is called in a separate thread and
   * g_desktop_app_info_new does some internal locking to
   * build up its cache of .desktop files, we're just exposing ourselves
   * to the possibility of a deadlock in another library
   * unnecessarly, so its better to just return an error
   * here and have the caller deal with it.
   *
   * https://phabricator.endlessm.com/T23650
   */
  g_set_error (error,
               EOS_COMPANION_APP_SERVICE_ERROR,
               EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID,
               "Application %s is not installed",
               app_id);
  return NULL;
}

static gboolean
lookup_eknservices_version (const gchar  *runtime_version,
                            gchar       **out_eknservices_name,
                            gchar       **out_search_provider_name,
                            GError      **error)
{
  g_return_val_if_fail (out_eknservices_name != NULL, FALSE);
  g_return_val_if_fail (out_search_provider_name != NULL, FALSE);

  static const struct {
    const gchar *runtime_version;
    const gchar *eknservices_name;
    const gchar *search_provider_name;
  } runtime_to_eknservices_versions[] = {
    { "1", "EknServices", "SearchProviderV1" },
    { "2", "EknServices2", "SearchProviderV2" },
    { "3", "EknServices2", "SearchProviderV2" },
    { "4", "EknServices3", "SearchProviderV3" },
    { "5", "EknServices3", "SearchProviderV3" }
  };
  static const gsize n_runtime_to_eknservices_version = G_N_ELEMENTS (runtime_to_eknservices_versions);
  gsize i = 0;

  for (; i < n_runtime_to_eknservices_version; ++i)
    {
      if (g_strcmp0 (runtime_version,
                     runtime_to_eknservices_versions[i].runtime_version) == 0)
        {
          *out_eknservices_name = g_strdup (runtime_to_eknservices_versions[i].eknservices_name);
          *out_search_provider_name = g_strdup (runtime_to_eknservices_versions[i].search_provider_name);
          return TRUE;
        }
    }

  g_set_error (error,
               EOS_COMPANION_APP_SERVICE_ERROR,
               EOS_COMPANION_APP_SERVICE_ERROR_UNSUPPORTED,
               "Attempted to find an EknServices version for %s, but it is unsupported",
               runtime_version);
  return FALSE;
}

static GPtrArray *
list_application_infos (EosCompanionAppServiceManagedCache  *cache,
                        GCancellable                        *cancellable,
                        GError                             **error)
{
  g_autoptr(GPtrArray) app_infos = g_ptr_array_new_with_free_func (g_object_unref);
  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *applications_directory_path = g_build_filename (*iter, "app", NULL);
      g_autoptr(GFile) flatpak_applications_directory = g_file_new_for_path (applications_directory_path);
      g_autoptr(GError) local_error = NULL;
      g_autoptr(GFileEnumerator) enumerator = g_file_enumerate_children (flatpak_applications_directory,
                                                                         G_FILE_ATTRIBUTE_STANDARD_NAME,
                                                                         G_FILE_QUERY_INFO_NONE,
                                                                         cancellable,
                                                                         &local_error);

      if (enumerator == NULL)
        {
          /* Directory not being found is fine, just means that this is not
           * a split system. */
          if (g_error_matches (local_error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND))
            continue;

          g_propagate_error (error, g_steal_pointer (&local_error));
          return NULL;
        }

      while (TRUE)
        {
          GFile *child = NULL;
          GFileInfo *info = NULL;
          g_autofree gchar *flatpak_directory = NULL;
          g_autofree gchar *runtime_spec = NULL;
          g_autofree gchar *runtime_name = NULL;
          g_autofree gchar *runtime_version = NULL;
          g_autofree gchar *app_name = NULL;
          g_autofree gchar *eknservices_name = NULL;
          g_autofree gchar *search_provider_name = NULL;
          g_autoptr(GDesktopAppInfo) app_info = NULL;
          g_autoptr(GError) check_app_error = NULL;
          gboolean is_compatible_app = FALSE;

          if (!g_file_enumerator_iterate (enumerator, &info, &child, cancellable, error))
            return NULL;

          if (!info)
            break;

          flatpak_directory = g_build_filename (applications_directory_path,
                                                g_file_info_get_name (info),
                                                NULL);

          /* Look inside the metadata for each flatpak to work out what runtime
           * it is using */
          if (!examine_flatpak_metadata (flatpak_directory, &app_name, &runtime_spec, &check_app_error))
            {
              g_message ("Flatpak at %s has a damaged installation and checking "
                         "its metadata failed with: %s, ignoring",
                         flatpak_directory,
                         check_app_error->message);
              continue;
            }

          if (!parse_runtime_spec (runtime_spec, &runtime_name, &runtime_version, &check_app_error))
            {
              g_message ("Flatpak %s had a damaged runtime spec %s (parsing failed "
                         "with: %s), ignoring",
                         app_name,
                         runtime_spec,
                         check_app_error->message);
              continue;
            }

          /* Check if the application is an eligible content app */
          if (!app_is_compatible (app_name,
                                  runtime_name,
                                  runtime_version,
                                  cache,
                                  &is_compatible_app,
                                  error))
            return NULL;

          if (!is_compatible_app)
            continue;

          app_info = load_desktop_info_key_file_for_app_id (app_name, &check_app_error);

          if (app_info == NULL)
            {
              g_message ("Flatpak %s does not have a loadable desktop file "
                         "(loading failed with: %s), ignoring",
                         app_name,
                         check_app_error->message);
              continue;
            }

          if (!g_app_info_should_show (G_APP_INFO (app_info)))
            continue;

          if (!lookup_eknservices_version (runtime_version,
                                           &eknservices_name,
                                           &search_provider_name,
                                           &check_app_error))
            {
              g_message ("Could not find corresponding EknServices verison for %s "
                         "(loading failed with: %s), ignoring",
                         app_name,
                         check_app_error->message);
              continue;
            }

          g_ptr_array_add (app_infos,
                           eos_companion_app_service_app_info_new (app_info,
                                                                   eknservices_name,
                                                                   search_provider_name));
        }
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
  EosCompanionAppServiceManagedCache *cache = g_task_get_task_data (task);
  g_autoptr(GPtrArray) application_infos_array =
    list_application_infos (cache, cancellable, &local_error);

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
eos_companion_app_service_list_application_infos (EosCompanionAppServiceManagedCache *cache,
                                                  GCancellable                       *cancellable,
                                                  GAsyncReadyCallback                 callback,
                                                  gpointer                            user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);

  g_task_set_task_data (task, g_object_ref (cache), g_object_unref);
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

static EosCompanionAppServiceAppInfo *
load_application_info (const gchar                         *app_id,
                       EosCompanionAppServiceManagedCache  *cache,
                       GError                             **error)
{
  g_autoptr(GDesktopAppInfo) app_info = NULL;
  g_autofree gchar *runtime_version = NULL;
  g_autofree gchar *eknservices_name = NULL;
  g_autofree gchar *search_provider_name = NULL;
  g_autofree gchar *runtime_spec = NULL;

  runtime_spec = eos_companion_app_service_get_runtime_spec_for_app_id (app_id,
                                                                        cache,
                                                                        error);

  if (runtime_spec == NULL)
    return FALSE;

  if (!parse_runtime_spec (runtime_spec, NULL, &runtime_version, error))
    return FALSE;

  if (!lookup_eknservices_version (runtime_version,
                                   &eknservices_name,
                                   &search_provider_name,
                                   error))
    return FALSE;

  app_info = load_desktop_info_key_file_for_app_id (app_id, error);

  if (app_info == NULL)
    return FALSE;

  return eos_companion_app_service_app_info_new (app_info,
                                                 eknservices_name,
                                                 search_provider_name);
}

typedef struct {
  gchar                              *name;
  EosCompanionAppServiceManagedCache *cache;
} LoadApplicationInfoData;

static LoadApplicationInfoData *
load_application_info_data_new (const gchar                        *name,
                                EosCompanionAppServiceManagedCache *cache)
{
  LoadApplicationInfoData *load_application_info_data = g_new0 (LoadApplicationInfoData, 1);

  load_application_info_data->name = g_strdup (name);
  load_application_info_data->cache = g_object_ref (cache);

  return load_application_info_data;
}

static void
load_application_info_data_free (LoadApplicationInfoData *load_application_info_data)
{
  g_clear_pointer (&load_application_info_data->name, g_free);
  g_clear_object (&load_application_info_data->cache);

  g_free (load_application_info_data);
}

static void
load_application_info_thread (GTask        *task,
                              gpointer      source,
                              gpointer      task_data,
                              GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  LoadApplicationInfoData *load_application_info_data = task_data;
  g_autoptr(EosCompanionAppServiceAppInfo) info = load_application_info (load_application_info_data->name,
                                                                         load_application_info_data->cache,
                                                                         &local_error);

  if (info == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task, g_steal_pointer (&info), g_object_unref);
}

void
eos_companion_app_service_load_application_info (const gchar                        *name,
                                                 EosCompanionAppServiceManagedCache *cache,
                                                 GCancellable                       *cancellable,
                                                 GAsyncReadyCallback                 callback,
                                                 gpointer                            user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_set_task_data (task,
                        load_application_info_data_new (name, cache),
                        (GDestroyNotify) load_application_info_data_free);
  g_task_run_in_thread (task, load_application_info_thread);
}

EosCompanionAppServiceAppInfo *
eos_companion_app_service_finish_load_application_info (GAsyncResult  *result,
                                                        GError       **error)
{
  g_return_val_if_fail (g_task_is_valid (result, NULL), NULL);

  return g_task_propagate_pointer (G_TASK (result), error);
}

static GStrv
load_colors_from_gresource_file (GResource  *resource,
                                 GError    **error)
{
  /* Since we will be using g_ptr_array_free with free_segment = FALSE, we
   * can't use g_autoptr here */
  GPtrArray *color_strings = NULL;
  gchar *unowned_input_stream_line = NULL;
  g_autoptr(GInputStream) css_stream = NULL;
  g_autoptr(GDataInputStream) css_data_stream = NULL;
  g_autoptr(GRegex) regex = g_regex_new ("^\\s*\\$([a-z0-9\\-]+)\\:\\s*(#[0-9a-f]+);\\s*$",
                                         G_REGEX_CASELESS,
                                         0,
                                         error);
  g_autoptr(GError) local_error = NULL;

  if (regex == NULL)
    return NULL;

  /* Pointer array allocated, remember to free it at every return point
   * post here */
  color_strings = g_ptr_array_new_with_free_func (g_free);
  css_stream = g_resource_open_stream (resource,
                                       "/app/overrides.scss",
                                       G_RESOURCE_LOOKUP_FLAGS_NONE,
                                       &local_error);

  if (css_stream == NULL)
    {
      if (g_error_matches (local_error,
                           G_RESOURCE_ERROR,
                           G_RESOURCE_ERROR_NOT_FOUND))
        {
          /* No scss file found in the resource, assume that this
           * application just has no colors to return and return the
           * empty array */
          g_ptr_array_add (color_strings, NULL);
          return (GStrv) g_ptr_array_free (color_strings, FALSE);
        }

      g_ptr_array_free (color_strings, TRUE);
      g_propagate_error (error, g_steal_pointer (&local_error));
      return NULL;
    }

  css_data_stream = g_data_input_stream_new (css_stream);

  while ((unowned_input_stream_line = g_data_input_stream_read_line (css_data_stream,
                                                                     NULL,
                                                                     NULL,
                                                                     &local_error)) != NULL)
    {
      g_autofree gchar *line = unowned_input_stream_line;
      g_autoptr(GMatchInfo) match_info = NULL;

      g_regex_match (regex, line, 0, &match_info);
      while (g_match_info_matches (match_info))
        {
          gchar *color_str = g_match_info_fetch (match_info, 2);

          g_ptr_array_add (color_strings, g_strdup (color_str));

          if (!g_match_info_next (match_info, &local_error))
            {
              /* Just because this function returned FALSE, does not
               * necessarily mean that it failed, check the error first
               * and propagate if necessary */
              if (local_error != NULL)
                {
                  g_propagate_error (error, g_steal_pointer (&local_error));
                  g_ptr_array_free (color_strings, TRUE);
                  return NULL;
                }
            }
        }
    }

  /* g_data_input_stream_read_line returns NULL either if it finished reading
   * all lines from the stream or an error occurred - check the error now. */
  if (local_error != NULL)
    {
      g_propagate_error (error, g_steal_pointer (&local_error));
      g_ptr_array_free (color_strings, TRUE);
      return NULL;
    }

  /* Need to append NULL to the end of the pointer array so that it
   * is a valid strv */
  g_ptr_array_add (color_strings, NULL);

  /* Steal the underlying data. */
  return (GStrv) g_ptr_array_free (color_strings, FALSE);
}

static GStrv
load_colors_for_app_id (const gchar  *app_id,
                        GError      **error)
{
  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();

  for (; *iter != NULL; ++iter)
    {
      g_autofree gchar *path = g_build_filename (*iter,
                                                 "app",
                                                 app_id,
                                                 "current",
                                                 "active",
                                                 "files",
                                                 "share",
                                                 app_id,
                                                 "app.gresource",
                                                 NULL);
      g_autoptr(GError) local_error = NULL;
      g_autoptr(GResource) resource = g_resource_load (path, &local_error);

      if (resource == NULL)
        {
          if (g_error_matches (local_error, G_FILE_ERROR, G_FILE_ERROR_NOENT))
            continue;

          g_propagate_error (error, g_steal_pointer (&local_error));
          return NULL;
        }

      return load_colors_from_gresource_file (resource, error);
    }

  /* Could not find a GResource file to load from. Return
   * EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID */
  g_set_error (error,
               EOS_COMPANION_APP_SERVICE_ERROR,
               EOS_COMPANION_APP_SERVICE_ERROR_INVALID_APP_ID,
               "Application %s is not installed",
               app_id);
  return NULL;
}

static void
load_application_colors_thread (GTask        *task,
                                gpointer      source,
                                gpointer      task_data,
                                GCancellable *cancellable)
{
  g_autoptr(GError) local_error = NULL;
  g_auto(GStrv) colors = load_colors_for_app_id ((const gchar *) task_data,
                                                 &local_error);

  if (colors == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task,
                         g_steal_pointer (&colors),
                         (GDestroyNotify) g_strfreev);
}

void
eos_companion_app_service_load_application_colors (const gchar         *app_id,
                                                   GCancellable        *cancellable,
                                                   GAsyncReadyCallback  callback,
                                                   gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);

  g_task_set_return_on_cancel (task, TRUE);
  g_task_set_task_data (task, g_strdup (app_id), g_free);
  g_task_run_in_thread (task, load_application_colors_thread);
}

GStrv
eos_companion_app_service_finish_load_application_colors (GAsyncResult  *result,
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

  GStrv iter = eos_companion_app_service_flatpak_install_dirs ();

  if (g_once_init_enter (&initialization_value))
    {
      theme = gtk_icon_theme_new ();

      for (; *iter != NULL; ++iter)
        {
          g_autofree gchar *icons_path = g_build_filename (*iter,
                                                           "exports",
                                                           "share",
                                                           "icons",
                                                           NULL);

          gtk_icon_theme_prepend_search_path (theme, icons_path);
        }
      g_once_init_leave (&initialization_value, 1);
    }

  return theme;
}

static GBytes *
pixbuf_to_png_bytes (GdkPixbuf     *pixbuf,
                     GError       **error)
{
  g_autofree gchar *buffer = NULL;
  gsize buffer_size = 0;

  if (!gdk_pixbuf_save_to_buffer (pixbuf, &buffer, &buffer_size, "png", error, NULL))
    return NULL;

  return g_bytes_new_take (g_steal_pointer (&buffer), buffer_size);
}

static GBytes *
load_icon_info_from_result_to_png_bytes (GtkIconInfo   *icon_info,
                                         GAsyncResult  *result,
                                         GError       **error)
{
  g_autoptr(GdkPixbuf) pixbuf = gtk_icon_info_load_icon_finish (icon_info,
                                                                result,
                                                                error);

  if (pixbuf == NULL)
    return NULL;

  return pixbuf_to_png_bytes (pixbuf, error);
}

static void
on_icon_pixbuf_loaded (GObject       *source,
                       GAsyncResult  *result,
                       gpointer       user_data)
{
  g_autoptr(GTask) task = G_TASK (user_data);
  g_autoptr(GError) local_error = NULL;
  g_autoptr(GBytes) icon_bytes = load_icon_info_from_result_to_png_bytes (GTK_ICON_INFO (source),
                                                                          result,
                                                                          &local_error);

  if (icon_bytes == NULL)
    {
      g_task_return_error (task, g_steal_pointer (&local_error));
      return;
    }

  g_task_return_pointer (task, g_steal_pointer (&icon_bytes), (GDestroyNotify) g_bytes_unref);
}

#define ICON_SIZE 64

/* We'll do this to avoid blocking the main thread on loading image data */
void
eos_companion_app_service_load_application_icon_data_async (const gchar         *icon_name,
                                                            GCancellable        *cancellable,
                                                            GAsyncReadyCallback  callback,
                                                            gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new (NULL, cancellable, callback, user_data);
  g_autoptr(GtkIconInfo) icon_info = NULL;

  g_task_set_return_on_cancel (task, TRUE);

  /* Load the icon info from the cache (which may mutate the cache, so we
   * cannot do it in a worker thread) and then load the icon asynchronously
   *
   * See https://phabricator.endlessm.com/T22584 */
  icon_info = gtk_icon_theme_lookup_icon_for_scale (get_singleton_icon_theme (),
                                                    icon_name,
                                                    ICON_SIZE,
                                                    1,
                                                    0);

  gtk_icon_info_load_icon_async (icon_info,
                                 cancellable,
                                 on_icon_pixbuf_loaded,
                                 g_steal_pointer (&task));
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

static GStrv
hardcoded_flatpak_install_dirs (void)
{
  static const gchar *dirs[] = {
    EOS_COMPANION_APP_SERVICE_SYSTEM_FLATPAK_INSTALL_DIR,
    EOS_COMPANION_APP_SERVICE_EXTERNAL_FLATPAK_INSTALL_DIR,
    NULL
  };

  return (GStrv) dirs;
}

static GStrv
override_flatpak_install_dirs (void)
{
  static const gchar *dirs[3];

  /* Mutating global static storage here is not ideal, but it
   * saves us from having to allocate/deallocate memory all the time. */
  dirs[0] = g_getenv ("EOS_COMPANION_APP_FLATPAK_SYSTEM_DIR");
  dirs[1] = g_getenv ("EOS_COMPANION_APP_FLATPAK_USER_DIR");
  dirs[2] = NULL;

  return (GStrv) dirs;
}

GStrv
eos_companion_app_service_flatpak_install_dirs (void)
{
  GStrv override_dirs = override_flatpak_install_dirs ();

  if (override_dirs[0] != NULL)
    return override_dirs;

  return hardcoded_flatpak_install_dirs ();
}

G_DEFINE_QUARK (eos-companion-app-service-error, eos_companion_app_service_error)

