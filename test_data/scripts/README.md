# Generation of testing content

The scripts in this directory exist to generate binary content archives
for the tests. We generate this binary content at source-checkin time as
opposed to test time since it allows us to avoid having a dependency
on build tools such as basin, which may break our build.

To regenerate the content shards and gresource files use:

    make test-content

and check in the resulting binary files.

In general, the fact that we have such scripts is a compromise for the
fact that we cannot effectively mock out the Eknc engine and shards
at runtime. At a later point we will need to break the dependency on
Eknc and access content through an SDK-neutral abstraction layer. At that
point we should drop these scripts and the hardcoded content and instead
mock out at that layer instead.

See https://github.com/endlessm/eos-companion-app-integration/pull/55/files#r170518968
for a more complete discussion.

See also https://phabricator.endlessm.com/T21320 for the relevant ticket.
