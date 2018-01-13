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

#include <glib.h>
#include <gio/gio.h>
#include <sysexits.h>

/* main() exit codes. */
enum
{
  EXIT_OK = EX_OK,
  EXIT_FAILED = 1,
  EXIT_INVALID_ARGUMENTS = 2
};

static int
usage (GOptionContext *context,
       const gchar    *error_message,
       ...) G_GNUC_PRINTF (2, 3);

static int
usage (GOptionContext *context,
       const gchar    *error_message,
       ...)
{
  va_list ap;
  g_autofree gchar *formatted_message = NULL;
  g_autofree gchar *help = NULL;

  /* Format the arguments. */
  va_start (ap, error_message);
  formatted_message = g_strdup_vprintf (error_message, ap);
  va_end (ap);

  /* Include the usage. */
  help = g_option_context_get_help (context, TRUE, NULL);
  g_printerr ("%s: %s\n\n%s\n", g_get_prgname (), formatted_message, help);

  return EXIT_INVALID_ARGUMENTS;
}

static gchar *candidate_config_files_priority_order[] = {
  SYSCONFDIR "/eos-companion-app/config.ini",
  LOCALSTATEDIR "/lib/eos-companion-app/config.ini",
  DATADIR "/eos-companion-app/config.ini",
  NULL
};

static GKeyFile *
read_one_config_file (GError **error)
{
  gsize i;
  g_autoptr(GKeyFile) key_file = g_key_file_new ();
  g_autoptr(GError) local_error = NULL;

  for (i = 0; candidate_config_files_priority_order[i] != NULL; ++i)
    {
      if (!g_key_file_load_from_file (key_file,
                                      candidate_config_files_priority_order[i],
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

      return g_steal_pointer (&key_file);
    }

  g_set_error (error, G_IO_ERROR, G_IO_ERROR_FAILED, "Could not find a configuration file");
  return NULL;
}

#define COMPANION_APP_SECTION_NAME "Companion App"
#define ENABLED_KEY_NAME "enabled"

static gboolean
parse_config_file (GKeyFile *key_file, gboolean *enabled, GError **error)
{
  gboolean value;

  g_return_val_if_fail (enabled != NULL, FALSE);

  value = g_key_file_get_boolean (key_file,
                                  COMPANION_APP_SECTION_NAME,
                                  ENABLED_KEY_NAME,
                                  error);

  if (*error)
    return FALSE;

  *enabled = value;
  return TRUE;
}

#define AVAHI_SERVICE_FILE_LOCATION "/etc/avahi/services/companion-app.service"
#define COMPANION_APP_AVAHI_HELPER_BUS_NAME "com.endlessm.CompanionAppServiceAvahiHelper"
#define COMPANION_APP_AVAHI_HELPER_OBJECT_PATH "/com/endlessm/CompanionAppServiceAvahiHelper"
#define COMPANION_APP_AVAHI_HELPER_INTERFACE "com.endlessm.CompanionApp.AvahiHelper"

static gboolean
service_file_exists (void)
{
  return g_file_test (AVAHI_SERVICE_FILE_LOCATION, G_FILE_TEST_EXISTS);
}

static gboolean
make_call_to_avahi_helper (const gchar *method, GError **error)
{
  g_autoptr(GDBusConnection) connection = g_bus_get_sync (G_BUS_TYPE_SYSTEM,
                                                          NULL,
                                                          error);

  if (connection == NULL)
    return FALSE;

  if (!g_dbus_connection_call_sync (connection,
                                    COMPANION_APP_AVAHI_HELPER_BUS_NAME,
                                    COMPANION_APP_AVAHI_HELPER_OBJECT_PATH,
                                    COMPANION_APP_AVAHI_HELPER_INTERFACE,
                                    method,
                                    NULL,
                                    NULL,
                                    G_DBUS_CALL_FLAGS_NONE,
                                    -1,
                                    NULL,
                                    error))
    return FALSE;

  return TRUE;
}

static gboolean
update_state (GError **error)
{
  g_autoptr(GKeyFile) key_file = read_one_config_file (error);
  gboolean is_enabled = FALSE;

  if (key_file == NULL)
    return FALSE;

  if (!parse_config_file (key_file, &is_enabled, error))
    return FALSE;

  if (is_enabled && !service_file_exists ())
    {
      g_message ("Enabling Companion App Integration");

      if (!make_call_to_avahi_helper ("EnterDiscoverableMode", error))
        return FALSE;
    }
  else if (!is_enabled && service_file_exists ())
    {
      g_message ("Disabling Companion App Integration");

      if (!make_call_to_avahi_helper ("ExitDiscoverableMode", error))
        return FALSE;
    }

  return TRUE;
}

int
main (int argc, gchar **argv)
{
  g_autoptr(GError) error = NULL;
  g_autoptr(GOptionContext) context = NULL;

  GOptionEntry entries[] =
    {
      { NULL }
    };

  context = g_option_context_new ("— Endless OS Companion App Configuration Manager");
  g_option_context_add_main_entries (context, entries, NULL);
  g_option_context_set_summary (context,
                                "Update configuration for Endless OS Companion App");

  if (!g_option_context_parse (context, &argc, &argv, &error))
    return usage (context, "Failed to parse options: %s", error->message);

  if (!update_state (&error))
    {
      g_warning ("Failed to update state of companion app configuration: %s",
                 error->message);
      return EXIT_INVALID_ARGUMENTS;
    }

  return EXIT_OK;
}
