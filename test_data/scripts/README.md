# Generation of testing content

The scripts in this directory exist to generate a binary
gresource archive for the tests, so as to avoid having a dependency
on glib-compile-resources during the tests.

To regenerate the content shards and gresource files use:

    make test-data

and check in the resulting binary files.

See https://github.com/endlessm/eos-companion-app-integration/pull/55/files#r170518968
for a more complete discussion.

See also https://phabricator.endlessm.com/T21320 for the relevant ticket.
