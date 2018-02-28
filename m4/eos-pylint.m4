dnl Copyright 2017 Endless Mobile, Inc.
dnl
dnl Permission is hereby granted, free of charge, to any person obtaining a copy
dnl of this software and associated documentation files (the "Software"), to
dnl deal in the Software without restriction, including without limitation the
dnl rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
dnl sell copies of the Software, and to permit persons to whom the Software is
dnl furnished to do so, subject to the following conditions:
dnl
dnl The above copyright notice and this permission notice shall be included in
dnl all copies or substantial portions of the Software.
dnl
dnl THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
dnl IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
dnl FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
dnl AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
dnl LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
dnl FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
dnl IN THE SOFTWARE.
dnl
dnl Macros to check for pylint support
dnl
dnl Expand EOS_PYLINT_RULES in your Makefile.am to get access to a
dnl 'pylint' target which will run pylint over the files specified in
dnl EOS_PYLINT_FILES.
dnl
dnl Add run_pylint.pylint to TESTS to run pylint checks on make check

EOS_HAVE_PYLINT=no

PYLINT=notfound

AC_DEFUN_ONCE([EOS_PYLINT], [
    # Enable the --enable-pylint switch, although it will only be effective
    # if we can actually run pylint.
    AC_ARG_ENABLE([pylint], [
        AS_HELP_STRING([--enable-pylint],
            [Run code style and correctness checks when running tests @<:@default=yes@:>@])
    ])

    EOS_PYLINT_REQUESTED=yes
    AC_MSG_CHECKING([whether pylint checks were requested])
    AS_IF([test "x${enable_eslint}" = "xno"], [
        EOS_PYLINT_REQUESTED=no
    ])
    AC_MSG_RESULT([$EOS_PYLINT_REQUESTED])

    AS_IF([test "x$EOS_PYLINT_REQUESTED" = "xyes"], [
        # Need pylint in order to run pylint, obviously.
        AC_PATH_PROG([PYLINT], [pylint], [notfound])

        EOS_PYLINT_AVAILABLE=no
        AS_IF([test "x$PYLINT" != "xnotfound"], [
            EOS_PYLINT_AVAILABLE=yes
        ])

        AC_MSG_CHECKING([if we can run lint checks during tests])
        AC_MSG_RESULT([$EOS_PYLINT_AVAILABLE])
    ])

    AS_IF([test "x$EOS_PYLINT_AVAILABLE" = "xyes"], [
        EOS_PYLINT_RULES_HEADER='
EOS_PYLINT_ENVIRONMENT = \
	GI_TYPELIB_PATH="$(top_builddir):$${GI_TYPELIB_PATH:+:$$GI_TYPELIB_PATH}" \
	LD_LIBRARY_PATH="$(top_builddir)/.libs:$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	$(NULL)

pylint: $(EOS_PYLINT_FILES)
	$(EOS_PYLINT_ENVIRONMENT) $(PYLINT) --rcfile=$(abs_top_srcdir)/.pylintrc $(addprefix $(abs_top_srcdir)/,$(EOS_PYLINT_FILES))
'
    ], [
        EOS_PYLINT_RULES_HEADER='
pylint:
	@echo "pylint not available on this system"
'
    ])

    EOS_PYLINT_RULES_FOOTER='
run_pylint.pylint:
	echo "make pylint" >> run_pylint.pylint

PYLINT_LOG_COMPILER = bash
CLEANFILES += run_pylint.pylint
.PHONY: pylint
'

    EOS_PYLINT_RULES="$EOS_PYLINT_RULES_HEADER $EOS_PYLINT_RULES_FOOTER"
    AC_SUBST([EOS_PYLINT_RULES])
    AM_SUBST_NOTMAKE([EOS_PYLINT_RULES])
])
