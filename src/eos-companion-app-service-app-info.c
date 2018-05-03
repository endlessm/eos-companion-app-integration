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

#include "eos-companion-app-service-app-info.h"

typedef struct _EosCompanionAppServiceAppInfo {
  GObject object;
} EosCompanionAppServiceAppInfo;

typedef struct _EosCompanionAppServiceAppInfoPrivate
{
  /* The #GDesktopAppInfo for this application */
  GDesktopAppInfo *desktop_app_info;

  /* The "EknSerivces" name to use for this application (for instance
   * "EknServices2", "EknServices3") */
  gchar           *eknservices_name;

  /* The "SearchProvider" name to use for this application (for instance
   * "SearchProviderV2", "SearchProviderV3") */
  gchar           *search_provider_name;
} EosCompanionAppServiceAppInfoPrivate;

G_DEFINE_TYPE_WITH_PRIVATE (EosCompanionAppServiceAppInfo,
                            eos_companion_app_service_app_info,
                            G_TYPE_OBJECT)

enum {
  PROP_0,
  PROP_DESKTOP_APP_INFO,
  PROP_EKNSERVICES_NAME,
  PROP_SEARCH_PROVIDER_NAME,
  NPROPS
};

static GParamSpec *eos_companion_app_service_app_info_props [NPROPS] = { NULL, };

/**
 * eos_companion_app_service_app_info_get_desktop_app_info:
 * @info: A #EosCompanionAppServiceAppInfo
 *
 * Get the #GDesktopAppInfo for this #EosCompanionAppServiceAppInfo
 *
 * Returns: (transfer none): A #GDesktopAppInfo
 */
GDesktopAppInfo *
eos_companion_app_service_app_info_get_desktop_app_info (EosCompanionAppServiceAppInfo *info)
{
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (info);

  return priv->desktop_app_info;
}

/**
 * eos_companion_app_service_app_info_get_eknserivces_name:
 * @info: A #EosCompanionAppServiceAppInfo
 *
 * Get the EknServices name for this #EosCompanionAppServiceAppInfo
 *
 * Returns: (transfer none): The name of the corresponding EknServices
 */
const gchar *
eos_companion_app_service_app_info_get_eknservices_name (EosCompanionAppServiceAppInfo *info)
{
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (info);

  return priv->eknservices_name;
}

/**
 * eos_companion_app_service_app_info_get_search_provider_name:
 * @info: A #EosCompanionAppServiceAppInfo
 *
 * Get the SearchProvider name for this #EosCompanionAppServiceAppInfo
 *
 * Returns: (transfer none): The name of the corresponding SearchProvider
 */
const gchar *
eos_companion_app_service_app_info_get_search_provider_name (EosCompanionAppServiceAppInfo *info)
{
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (info);

  return priv->search_provider_name;
}

static void
eos_companion_app_service_app_info_init (EosCompanionAppServiceAppInfo *model)
{
}

static void
eos_companion_app_service_app_info_set_property (GObject      *object,
                                                 guint         prop_id,
                                                 const GValue *value,
                                                 GParamSpec   *pspec)
{
  EosCompanionAppServiceAppInfo *store = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (store);

  switch (prop_id)
    {
    case PROP_DESKTOP_APP_INFO:
      priv->desktop_app_info = g_value_dup_object (value);
      break;
    case PROP_EKNSERVICES_NAME:
      priv->eknservices_name = g_value_dup_string (value);
      break;
    case PROP_SEARCH_PROVIDER_NAME:
      priv->search_provider_name = g_value_dup_string (value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    }
}

static void
eos_companion_app_service_app_info_get_property (GObject    *object,
                                                 guint       prop_id,
                                                 GValue     *value,
                                                 GParamSpec *pspec)
{
  EosCompanionAppServiceAppInfo *store = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (store);

  switch (prop_id)
    {
    case PROP_DESKTOP_APP_INFO:
      g_value_set_object (value, priv->desktop_app_info);
      break;
    case PROP_EKNSERVICES_NAME:
      g_value_set_string (value, priv->eknservices_name);
      break;
    case PROP_SEARCH_PROVIDER_NAME:
      g_value_set_string (value, priv->search_provider_name);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    }
}

static void
eos_companion_app_service_app_info_finalize (GObject *object)
{
  EosCompanionAppServiceAppInfo *store = EOS_COMPANION_APP_SERVICE_APP_INFO (object);
  EosCompanionAppServiceAppInfoPrivate *priv = eos_companion_app_service_app_info_get_instance_private (store);

  g_clear_object (&priv->desktop_app_info);
  g_clear_pointer (&priv->eknservices_name, g_free);
  g_clear_pointer (&priv->search_provider_name, g_free);

  G_OBJECT_CLASS (eos_companion_app_service_app_info_parent_class)->finalize (object);
}

static void
eos_companion_app_service_app_info_class_init (EosCompanionAppServiceAppInfoClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->get_property = eos_companion_app_service_app_info_get_property;
  object_class->set_property = eos_companion_app_service_app_info_set_property;
  object_class->finalize = eos_companion_app_service_app_info_finalize;

  eos_companion_app_service_app_info_props[PROP_DESKTOP_APP_INFO] =
    g_param_spec_object ("desktop-app-info",
                         "Desktop AppInfo",
                         "The GDesktopAppInfo for this EosCompanionAppServiceAppInfo",
                         G_TYPE_DESKTOP_APP_INFO,
                         G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY);

  eos_companion_app_service_app_info_props[PROP_EKNSERVICES_NAME] =
    g_param_spec_string ("eknservices-name",
                         "EknServices Name",
                         "The name of the corresponding EknServices",
                         "",
                         G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY);

  eos_companion_app_service_app_info_props[PROP_SEARCH_PROVIDER_NAME] =
    g_param_spec_string ("search-provider-name",
                         "SearchProvider Name",
                         "The name of the corresponding SearchProvider",
                         "",
                         G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY);

  g_object_class_install_properties (object_class,
                                     NPROPS,
                                     eos_companion_app_service_app_info_props);
}

EosCompanionAppServiceAppInfo *
eos_companion_app_service_app_info_new (GDesktopAppInfo *desktop_app_info,
                                        const gchar     *eknservices_name,
                                        const gchar     *search_provider_name)
{
  return g_object_new (EOS_COMPANION_APP_SERVICE_TYPE_APP_INFO,
                       "desktop-app-info", desktop_app_info,
                       "eknservices-name", eknservices_name,
                       "search-provider-name", search_provider_name,
                       NULL);
}

