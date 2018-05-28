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

#include "eos-companion-app-installer-helper.h"

#include <cairo.h>
#include <errno.h>
#include <gio/gio.h>
#include <string.h>
#include <qrencode.h>

G_DEFINE_AUTOPTR_CLEANUP_FUNC (cairo_surface_t, cairo_surface_destroy)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (cairo_t, cairo_destroy)

static cairo_surface_t *
scale_image_surface (cairo_surface_t *src,
                     gsize            width,
                     gsize            height)
{
  g_autoptr(cairo_surface_t) dst = cairo_image_surface_create (CAIRO_FORMAT_RGB24,
                                                               width,
                                                               height);
  g_autoptr(cairo_t) cr = cairo_create (dst);

  cairo_scale (cr,
               width / ((gfloat) cairo_image_surface_get_width (src)),
               height / ((gfloat) cairo_image_surface_get_height (src)));

  cairo_set_source_surface (cr, src, 0, 0);
  cairo_pattern_set_filter (cairo_get_source (cr), CAIRO_FILTER_NEAREST);
  cairo_paint (cr);

  return g_steal_pointer (&dst);
}

G_DEFINE_AUTOPTR_CLEANUP_FUNC (QRcode, QRcode_free)

/**
 * eos_companion_app_offline_installer_generate_qr_code_surface:
 * @string: The string to encode (maximum length of X chars)
 * @target_width: How wide and tall to make the surface
 * @error: A #GError
 *
 * Generate a QR code from @string, using the highest level of error correction
 * and render it to a #cairo_surface_t with width @target_width and height
 * @target_width.
 *
 * If an error occurrs, it will be translated into a corresponding
 * %G_IO_ERROR and returned through @error as an outparam.
 *
 * Returns: (transfer full): The generated QR code as a #cairo_surface_t
 */
cairo_surface_t *
eos_companion_app_offline_installer_generate_qr_code_surface (const gchar  *string,
                                                              gsize         target_width,
                                                              GError      **error)
{
  g_autoptr(QRcode) qr_code = QRcode_encodeString (string,
                                                   0,
                                                   QR_ECLEVEL_H,
                                                   QR_MODE_8,
                                                   1);
  g_autoptr(cairo_surface_t) qr_surface = NULL;
  gint i = 0;
  gint size = 0;
  gint stride = 0;
  guint32 *bytes = NULL;

  if (qr_code == NULL)
    {
      g_autofree gchar *msg = g_strdup_printf ("Unable to encode QR code for string %s: %s",
                                               string,
                                               strerror (errno));
      g_set_error (error, G_IO_ERROR, g_io_error_from_errno (errno), "%s", msg);
      return NULL;
    }

  qr_surface = cairo_image_surface_create (CAIRO_FORMAT_RGB24,
                                           qr_code->width,
                                           qr_code->width);
  size = qr_code->width * qr_code->width;
  stride = cairo_image_surface_get_stride (qr_surface);
  bytes = (guint32 *) cairo_image_surface_get_data (qr_surface);

  /* According to the qrencode documentation, the data member of the
   * QRcode is not an image on its own, but rather an 8-bit number of
   * which the least significant bit is set if the corresponding module
   * should be black and not set if the corresponding module should be white.
   *
   * So, we loop through the QR code and set bits in the corresponding image
   * surface as appropriate.
   */
  for (; i < size; ++i)
    {
      gint row_idx = i / qr_code->width;
      gint col_idx = i % qr_code->width;

      /* Stride is in bytes, since we are writing 4 bytes at a time, we need
       * to divide by 4 */
      gint image_offset = row_idx * (stride / 4) + col_idx;
      gchar value = (qr_code->data[i] & (1 << 0)) != 0 ? 0 : 0xffffff;

      bytes[image_offset] = value;
    }

  return scale_image_surface (qr_surface, target_width, target_width);
}

/**
 * eos_companion_app_offline_installer_init:
 *
 * Initialize the helper library. This is needed by some language bindings
 * in order to ensure that corresponding static resources are initialized
 * as well.
 */
void
eos_companion_app_offline_installer_init (void)
{
}
