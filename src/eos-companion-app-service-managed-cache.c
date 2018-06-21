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

#include "eos-companion-app-service-managed-cache.h"
#include "eos-companion-app-service-managed-cache-private.h"

typedef struct _EosCompanionAppServiceManagedCache {
  GObject object;
} EosCompanionAppServiceManagedCache;

typedef struct _EosCompanionAppServiceManagedCachePrivate
{
  GMutex mutex;
  GHashTable *cache_tree;
} EosCompanionAppServiceManagedCachePrivate;

G_DEFINE_TYPE_WITH_PRIVATE (EosCompanionAppServiceManagedCache,
                            eos_companion_app_service_managed_cache,
                            G_TYPE_OBJECT)

typedef struct {
  GMutex      mutex;
  GHashTable *ht;
} LockedCache;

static LockedCache *
locked_cache_new (GDestroyNotify value_destroy_func)
{
  LockedCache *cache = g_new0 (LockedCache, 1);

  cache->ht = g_hash_table_new_full (g_str_hash,
                                     g_str_equal,
                                     g_free,
                                     value_destroy_func);
  g_mutex_init (&cache->mutex);

  return cache;
}

static void
locked_cache_free (LockedCache *cache)
{
  g_mutex_lock (&cache->mutex);
  g_hash_table_unref (cache->ht);
  g_mutex_unlock (&cache->mutex);

  g_free (cache);
}

static GHashTable *
locked_cache_lock (LockedCache *cache)
{
  g_mutex_lock (&cache->mutex);
  return cache->ht;
}

static void
locked_cache_unlock (LockedCache *cache)
{
  g_mutex_unlock (&cache->mutex);
}

/**
 * eos_companion_app_service_managed_cache_clear:
 * @cache: A #EosCompanionAppServiceManagedCache.
 *
 * Clear all the entries in this #EosCompanionAppServiceManagedCache, forcing
 * them to be regenerated if required.
 */
void
eos_companion_app_service_managed_cache_clear (EosCompanionAppServiceManagedCache *cache)
{
  EosCompanionAppServiceManagedCachePrivate *priv = eos_companion_app_service_managed_cache_get_instance_private (cache);

  g_mutex_lock (&priv->mutex);
  g_hash_table_remove_all (priv->cache_tree);
  g_mutex_unlock (&priv->mutex);
}

/**
 * eos_companion_app_service_managed_cache_lock_subcache: (skip)
 * @cache: An #EosCompanionAppServiceManagedCache.
 * @key: The key to lock the subcache with.
 * @value_destroy: A #GDestroyNotify for the value type of the subcache, if
 *                 it needs to be created.
 *
 * Get a #GHashTable subcache from a #EosCompanionAppServiceManagedCache. The
 * subcache is in a "locked" state, meaning that no other thread can read from
 * or write to this subcache. Once the caller is done with the subcache, it
 * should return it by using eos_companion_app_service_managed_cache_unlock_subcache.
 *
 * Returns: (transfer none): A #GHashTable.
 */
GHashTable *
eos_companion_app_service_managed_cache_lock_subcache (EosCompanionAppServiceManagedCache *cache,
                                                       const gchar                        *key,
                                                       GDestroyNotify                      value_destroy)
{
  EosCompanionAppServiceManagedCachePrivate *priv = eos_companion_app_service_managed_cache_get_instance_private (cache);
  gpointer subcache = NULL;

  /* Critical section: creating subcache if it does not exist */
  g_autoptr(GMutexLocker) locker = g_mutex_locker_new (&priv->mutex);

  if ((subcache = g_hash_table_lookup (priv->cache_tree, key)))
    return locked_cache_lock ((LockedCache *) subcache);

  subcache = locked_cache_new (value_destroy);
  g_hash_table_insert (priv->cache_tree, g_strdup (key), subcache);

  return locked_cache_lock ((LockedCache *) subcache);
}

/**
 * eos_companion_app_service_managed_cache_unlock_subcache: (skip)
 * @cache: An #EosCompanionAppServiceManagedCache.
 * @key: The key for the cache to return.
 *
 * Return the subcache to the managed cache, thus unlocking it for other threads
 * to use. If the subcache with that key does not exist, this function will
 * have no effect.
 */
void
eos_companion_app_service_managed_cache_unlock_subcache (EosCompanionAppServiceManagedCache *cache,
                                                         const gchar                        *key)
{
  EosCompanionAppServiceManagedCachePrivate *priv = eos_companion_app_service_managed_cache_get_instance_private (cache);
  gpointer subcache = NULL;

  /* Critical section: creating subcache if it does not exist */
  g_autoptr(GMutexLocker) locker = g_mutex_locker_new (&priv->mutex);

  if ((subcache = g_hash_table_lookup (priv->cache_tree, key)))
    locked_cache_unlock ((LockedCache *) subcache);
}

static void
eos_companion_app_service_managed_cache_init (EosCompanionAppServiceManagedCache *cache)
{
  EosCompanionAppServiceManagedCachePrivate *priv = eos_companion_app_service_managed_cache_get_instance_private (cache);

  g_mutex_init (&priv->mutex);
  priv->cache_tree = g_hash_table_new_full (g_str_hash,
                                            g_str_equal,
                                            g_free,
                                            (GDestroyNotify) locked_cache_free);
}

static void
eos_companion_app_service_managed_cache_finalize (GObject *object)
{
  EosCompanionAppServiceManagedCache *cache = EOS_COMPANION_APP_SERVICE_MANAGED_CACHE (object);
  EosCompanionAppServiceManagedCachePrivate *priv = eos_companion_app_service_managed_cache_get_instance_private (cache);

  g_clear_pointer (&priv->cache_tree, g_hash_table_unref);

  G_OBJECT_CLASS (eos_companion_app_service_managed_cache_parent_class)->finalize (object);
}

static void
eos_companion_app_service_managed_cache_class_init (EosCompanionAppServiceManagedCacheClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->finalize = eos_companion_app_service_managed_cache_finalize;
}

EosCompanionAppServiceManagedCache *
eos_companion_app_service_managed_cache_new (void)
{
  return g_object_new (EOS_COMPANION_APP_SERVICE_TYPE_MANAGED_CACHE, NULL);
}

