AC_PREREQ(2.63)
AC_INIT([eos-companion-app-integration],
        [0.0.0],
        [https://github.com/endlessm/eos-companion-app-integration],
        [eos-companion-service],
        [https://github.com/endlessm/eos-companion-app-integration])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([Makefile.am])
AM_INIT_AUTOMAKE([1.11 tar-ustar dist-xz no-dist-gzip -Wno-portability subdir-objects])
AM_MAINTAINER_MODE([enable])
m4_ifdef([AM_SILENT_RULES],[AM_SILENT_RULES([no])])

AM_PATH_PYTHON([3.4])

GETTEXT_PACKAGE=$PACKAGE_NAME
AC_SUBST(GETTEXT_PACKAGE)

AC_PROG_CC
AM_PROG_CC_C_O
LT_INIT([disable-static])

# Set up GObject-Introspection
GOBJECT_INTROSPECTION_CHECK([1.30.0])

PKG_PROG_PKG_CONFIG([0.22])

# Python major version
AC_PATH_PROG([PYTHON3], [python3], [notfound])
AS_IF([test "x$PYTHON3" = "xnotfound"],
    [AC_MSG_ERROR([Could not find python3])])
AC_ARG_VAR([PYTHON3], [Path to python3])
pythonminorversion=$($PYTHON3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
AC_SUBST([pythonminorversion])

# glib-mkenums
AC_PATH_PROG([GLIB_MKENUMS],[glib-mkenums])
AS_IF([test "$GLIB_MKENUMS" == ""],[
  AC_MSG_ERROR([glib-mkenums not found])
])

GLIB_GSETTINGS
PKG_CHECK_MODULES([EOS_COMPANION_APP], [
  avahi-glib
  avahi-gobject
  eos-knowledge-content-0
  gdk-pixbuf-2.0
  glib-2.0
  gio-2.0
  gio-unix-2.0
  gtk+-3.0
  libsoup-2.4
])

AC_CONFIG_FILES([
  Makefile
])
AC_OUTPUT
