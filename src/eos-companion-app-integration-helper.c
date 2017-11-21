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

#include "eos-companion-app-integration-helper.h"

#include <string.h>

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
  soup_message_set_response (message,
                             content_type,
                             SOUP_MEMORY_COPY,
                             request,
                             strlen (request));
}

G_DEFINE_QUARK (eos-companion-app-service-error-quark, eos_companion_app_service_error)

