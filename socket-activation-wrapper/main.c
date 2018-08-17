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

#include <systemd/sd-daemon.h>

/* main() exit codes. */
enum
{
  EXIT_OK = EX_OK,
  EXIT_FAILED = 1
};

static gboolean
detect_sockets_and_launch (const gchar **argv,
                           int          *out_exit_status,
                           GError      **error)
{
  g_assert (out_exit_status != NULL);
  int fds_count = sd_listen_fds (0);

  if (fds_count > 1)
    {
      g_set_error (error,
                   G_IO_ERROR,
                   G_IO_ERROR_FAILED,
                   "Too many file descriptors received: %d",
                   fds_count);
      return FALSE;
    }

  /* We had a socket activation file descriptor.
   * Put it into an environment variable for the child
   * process to see. We need to use an environment
   * variable since it is possible that the same file
   * descriptor that the child would usually use (3)
   * might be used by some other connection if the child
   * was launched outside of systemd. */
  if (fds_count == 1)
    {
      g_autofree char *value = g_strdup_printf ("%d", SD_LISTEN_FDS_START);
      g_setenv ("EOS_COMPANION_APP_SERVICE_LISTEN_FD",
                value,
                TRUE);
    }

  return g_spawn_sync (NULL,
                       (gchar **) argv,
                       NULL,
                       G_SPAWN_LEAVE_DESCRIPTORS_OPEN |
                       G_SPAWN_CHILD_INHERITS_STDIN |
                       G_SPAWN_SEARCH_PATH,
                       NULL,
                       NULL,
                       NULL,
                       NULL,
                       out_exit_status,
                       error);
}

int
main (int argc, gchar **argv)
{
  g_autoptr(GError) error = NULL;
  int exit_status = 0;

  if (!detect_sockets_and_launch ((const gchar **) &argv[1], &exit_status, &error))
    {
      g_warning ("Failed to detect sockets and launch Companion App Service: %s",
                 error->message);
      return EXIT_FAILED;
    }

  return exit_status;
}
