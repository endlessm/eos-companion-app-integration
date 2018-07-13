AC_PREREQ(2.63)
AC_INIT([eos-companion-app-integration],
        [0.0.0],
        [https://github.com/endlessm/eos-companion-app-integration],
        [eos-companion-service],
        [https://github.com/endlessm/eos-companion-app-integration])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([Makefile.am])
AM_INIT_AUTOMAKE([1.11 tar-ustar dist-xz no-dist-gzip -Wno-portability subdir-objects parallel-tests])
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

# glib-compile-resources
AC_PATH_PROG([GLIB_COMPILE_RESOURCES],[glib-compile-resources])
AS_IF([test "$GLIB_COMPILE_RESOURCES" == ""],[
  AC_MSG_ERROR([glib-compile-resources not found])
])

systemdsystemunitdir="$($PKG_CONFIG systemd --variable=systemdsystemunitdir)"
dnl Allow overriding systemdsystemunitdir during distcheck in order to trick
dnl Automake into allowing an install outside of $prefix
AC_ARG_WITH([systemdsystemunitdir],
  [AS_HELP_STRING([--with-systemdsystemunitdir=PATH], [directory for systemd service files])],
  [systemdsystemunitdir="$withval"])
AC_SUBST([systemdsystemunitdir])

ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS=""

AC_ARG_ENABLE([service], [companion app HTTP service], [
  EOS_COMPANION_APP_SERVICE_ENABLED=$enableval
], [
  EOS_COMPANION_APP_SERVICE_ENABLED=yes
])

AC_ARG_ENABLE([integration], [companion app OS integration], [
  EOS_COMPANION_APP_INTEGRATION_ENABLED=$enableval
], [
  EOS_COMPANION_APP_INTEGRATION_ENABLED=no
])

GLIB_GSETTINGS
AS_IF([test "x$EOS_COMPANION_APP_SERVICE_ENABLED" = "xyes"], [
  PKG_CHECK_MODULES([EOS_COMPANION_APP_SERVICE], [
    eos-shard-0
    gdk-pixbuf-2.0
    glib-2.0
    gio-2.0
    gio-unix-2.0
    gtk+-3.0
    libsoup-2.4
  ])
  ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --enable-service"
], [
  ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --disable-service"
])
AM_CONDITIONAL([EOS_COMPANION_APP_SERVICE_ENABLED], [test "x$EOS_COMPANION_APP_SERVICE_ENABLED" = "xyes"])

AS_IF([test "x$EOS_COMPANION_APP_INTEGRATION_ENABLED" = "xyes"], [
  PKG_CHECK_MODULES([EOS_COMPANION_APP_INTEGRATION], [
    glib-2.0
    gio-2.0
    gio-unix-2.0
  ])
  ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --enable-integration"
], [
  ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --disable-integration"
])

# We need to specify the literal /var and not $(localstatedir), since
# $(localstatedir) will be /app/var when building inside of the
# flatpak jail, which is not what we want
AC_ARG_WITH(system-install-dir,
           [AS_HELP_STRING([--with-system-install-dir=DIR],
                           [Location of the system installation [LOCALSTATEDIR/flatpak]])],
           [],
           [with_system_install_dir="/var/lib/flatpak"])
SYSTEM_INSTALL_DIR=$with_system_install_dir
ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --with-system-install-dir=$SYSTEM_INSTALL_DIR"
AC_SUBST(SYSTEM_INSTALL_DIR)

AC_ARG_WITH(external-install-dir,
           [AS_HELP_STRING([--with-external-install-dir=DIR],
                           [Location of the external installation [LOCALSTATEDIR/endless-extra/flatpak]])],
           [],
           [with_external_install_dir="/var/endless-extra/flatpak"])
EXTERNAL_INSTALL_DIR=$with_external_install_dir
ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS="$ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS --with-external-install-dir=$EXTERNAL_INSTALL_DIR"
AC_SUBST(EXTERNAL_INSTALL_DIR)

AM_CONDITIONAL([EOS_COMPANION_APP_INTEGRATION_ENABLED], [test "x$EOS_COMPANION_APP_INTEGRATION_ENABLED" = "xyes"])
AC_SUBST([ADDITIONAL_DISTCHECK_CONFIGURE_FLAGS])

# Check for some tools that we'll need if we're going to be doing
# any testing
AC_CHECK_PROG([HAVE_PYTHON3], [python3], ["yes"], ["no"])
AC_MSG_CHECKING([if tests can be run on this build])

# Need to have some odd formatting here due to the fact that
# an if-condition line on a shell script must end with either
# a logical operand or a semicolon
AS_IF([
  test "x$HAVE_PYTHON3" == "xyes"], [
  HAVE_TESTING_PROGS="yes"
], [
  HAVE_TESTING_PROGS="no"
])
AC_MSG_RESULT([$HAVE_TESTING_PROGS])
AM_CONDITIONAL([EOS_COMPANION_APP_SERVICE_ENABLE_TESTING], [test "x$HAVE_TESTING_PROGS" == "xyes"])

EOS_PYLINT

AC_CONFIG_FILES([
  Makefile
])
AC_OUTPUT
