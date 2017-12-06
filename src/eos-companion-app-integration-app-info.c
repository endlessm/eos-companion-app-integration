/*
 * Copyright © 2017 Endless Mobile, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library. If not, see <http://www.gnu.org/licenses/>.
 *
 * Authors:
 *       Sam Spilsbury <sam@endlessm.com>
 */

#include <glib-object.h>
#include "eos-companion-app-integration-app-info.h"

typedef struct _EosCompanionAppServiceAppInfoPrivate
{
  gchar *display_name;
  gchar *app_id;
} EosCompanionAppServiceAppInfoPrivate;

G_DEFINE_TYPE_WITH_PRIVATE (EosCompanionAppServiceAppInfo,
                            eos_companion_app_service_app_info,
                            G_TYPE_OBJECT)

enum {
  PROP_0,

  PROP_APP_ID,
  PROP_DISPLAY_NAME,
};

static void
eos_companion_app_service_app_info_finalize (GObject *object)
{
  EosCompanionAppServiceAppInfo *info = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (info);

  g_clear_pointer (&priv->display_name, g_free);
  g_clear_pointer (&priv->app_id, g_free);

  G_OBJECT_CLASS (eos_companion_app_service_app_info_parent_class)->finalize (object);
}

static void
eos_companion_app_service_app_info_set_property (GObject      *object,
                                                 guint         prop_id,
                                                 const GValue *value,
                                                 GParamSpec   *pspec)
{
  EosCompanionAppServiceAppInfo *self = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (self);

  switch (prop_id)
    {
    case PROP_APP_ID:
      g_clear_pointer (&priv->app_id, g_free);
      priv->app_id = g_value_dup_string (value);
      break;

    case PROP_DISPLAY_NAME:
      g_clear_pointer (&priv->display_name, g_free);
      priv->display_name = g_value_dup_string (value);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
    }
}

static void
eos_companion_app_service_app_info_get_property (GObject    *object,
                                                 guint       prop_id,
                                                 GValue     *value,
                                                 GParamSpec *pspec)
{
  EosCompanionAppServiceAppInfo *self = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (self);

  switch (prop_id)
    {
    case PROP_DISPLAY_NAME:
      g_value_set_string (value, priv->display_name);
      break;

    case PROP_APP_ID:
      g_value_set_string (value, priv->app_id);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
    }
}

static void
eos_companion_app_service_app_info_class_init (EosCompanionAppServiceAppInfoClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->get_property = eos_companion_app_service_app_info_get_property;
  object_class->set_property = eos_companion_app_service_app_info_set_property;
  object_class->finalize = eos_companion_app_service_app_info_finalize;

  /**
   * EosCompanionAppServiceAppInfo:app-id:
   *
   * The ID for the application.
   */
  g_object_class_install_property (object_class,
                                   PROP_APP_ID,
                                   g_param_spec_string ("app-id",
                                                        "App ID",
                                                        "Application ID",
                                                        NULL,
                                                        G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY));

  /**
   * EosCompanionAppServiceAppInfo:display-name:
   *
   * The display name for the application.
   */
  g_object_class_install_property (object_class,
                                   PROP_DISPLAY_NAME,
                                   g_param_spec_string ("display-name",
                                                        "Display Name",
                                                        "Display name of the application",
                                                        NULL,
                                                        G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY));
}

static void
eos_companion_app_service_app_info_init (EosCompanionAppServiceAppInfo *self)
{
}

EosCompanionAppServiceAppInfo *
eos_companion_app_service_app_info_new (const gchar *app_id,
                                        const gchar *display_name)
{
  return g_object_new (EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO,
                       "app-id", app_id,
                       "display-name", display_name,
                       NULL);
}
