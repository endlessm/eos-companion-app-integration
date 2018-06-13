# EOS Companion App Service OS Integration
This document is the technical reference for how the OS Integration described
in EOS Companion App works. It describes all the various services and
configuration files that exist and how they are used.


## Integration

### Design Requirements
1. **Socket Activation**: Because the Companion App Service is a Python
                          Webserver and is quite memory hungry, we do not
                          want it to be running all the time. We only want
                          it to be running while the Companion App is making
                          requests to the computer.
2. **Discoverability**: Regardless of whether or not the server is running,
                        it should always be discoverable by the app.
3. **Computer Identification**: Each computer should broadcast some unique
                                piece of data so that the Companion App can
                                identify it.
4. **Compatibility**: The Companion App Service should be able to access content
                      no matter what SDK an App is built against. The structure
                      of the OS Integration should permit this.

### Overview
The following diagram provides an overview of how everything relates to each
other (see [EOS Companion App | OS Integration | Diagram](https://docs.google.com/drawings/d/12qPHFOjPVfj-XZJh-zdFWqjvcpLwtURKaXuw2252jKo/edit?usp=sharing)
for a larger version).

### Underlying Service
The underlying eos-companion-app-service application is a Python application
that starts a RESTful Webserver on port 1110. The behaviour of the service
itself is described in [API](/docs/API.md).

The service itself exists as part of a flatpak,
com.endlessm.CompanionAppService. This encapsulates the part of the service
that does the HTTP request servicing, but not the mDNS discoverability.

As part of its sandbox, the flatpak only has read-only access to files within
the com.endlessm.Platform runtime and to exported flatpaks in
`/var/lib/flatpak`.

The service will run for however long it takes to service a request, plus
twenty seconds, with the twenty second countdown timer being reset every time
a new request is made to the already running service.

### Companion App Systemd Service
Since the Companion App Service may be spawned by socket activation, it must
be run as a systemd service. However, given that it is not running as the
logged in user, special care is taken to ensure that the service is
appropriately sandboxed. The service runs as the `companion-app-helper` user,
which does not have superuser privileges.

The systemd service has a dependency on
`/etc/avahi/services/companion-app.service` being available on-disk, and thus
on the service being discoverable. If that file is not present, the
corresponding systemd service will not start and socket activation will fail,
resulting in a rejected connection.

### Socket Activation
The `/lib/systemd/system/eos-companion-app.socket` file is installed to spawn
`eos-companion-app-service` (if it is not already running) when an external
client attempts to connect to port 1110.

Upon spawning the process, the process will attempt to start listening for
connections using

`eos_companion_app_service_soup_server_listen_on_sd_fd_or_port`. This function
will first attempt to read fd 3 (the systemd socket activation fd) for
connections and if that fails, listen on all interfaces on port 1110.

Note that socket activation will silently fail and the connection will be
rejected if the corresponding `/lib/systemd/system/eos-companion-app.service`
is unable to start.

### Discoverability
Discoverability is managed by using `/etc/avahi/services` as opposed to
registering an avahi service at runtime. This allows us to remain discoverable
even whilst the service is not running.

The specific file is `/etc/avahi/service/companion-app.service`. If this file
is present, the invariant is that the companion app service is an enabled
state and is discoverable. The file specifies a single TXT record,
`ServerUUID`, which is defined to have the same value as that in
`/etc/machine-id` (a single universally unique identifier for that machine,
generated at boot time).

The file should not be written by any process other than
`eos-companion-app-avahi-helper` since that process will maintain the
invariants around the Companion App’s state and the contents of the file.

### Avahi Helper
The aforementioned `eos-companion-app-avahi-helper` process is responsible for
managing the state of the `/etc/avahi/services/companion-app.service` file. It
runs as the companion-app-helper user which itself is a member of the
`avahi-service-writers` group (such that it has permission to write to
`/etc/avahi/services/` but nowhere else).

The helper is a python script that is activatable by making a dbus call on the
`com.endlessm.CompanionAppServiceAvahiHelper` name at the object path
`/com/endlessm/CompanionAppServiceAvahiHelper` on the interface
`com.endlessm.CompanionApp.AvahiHelper`.

Supported methods are (no arguments, no return value):

`EnterDiscoverableMode`: Enable Discoverability by writing the
                         `/etc/avahi/services/companion-app.service` file
                         and setting the "Enabled" key
                         in `/etc/eos-companion-app/config.ini` to true.
                         The Avahi daemon watches the services directory
                         and will automatically create a new service on mDNS.

`ExitDiscoverableMode`: Disable Discoverability by deleting the
                        `/etc/avahi/services/companion-app.service` file
                        and setting the "Enabled" key in
                        `/etc/eos-companion-app/config.ini` to false.
                        The Avahi daemon watches the services directory
                        and will automatically destroy the service on mDNS.

Supported properties are:

`Discoverable`: boolean, whether the service is enabled and in a discoverable
                state, determined by querying `/etc/avahi/services/companion-app.service`
                for existence.

### Configuration Manager
Since the contents of the Avahi service file differ from system to system, it
is not possible to ship the Avahi service file on images or the ostree by
default. Instead, a configuration manager binary is shipped which uses
eos-companion-app-avahi-helper to enable and disable discoverability and the
service.

It is anticipated that the configuration of the Companion App Service should
be modifiable by Endless, Image Distributors and by Local Administrators, in
ascending priority order. Each user should modify the following files:

Endless: `/usr/share/eos-companion-app/config.ini`
Image Distributors: `/var/lib/eos-companion-app/config.ini`
Local Administrators: `/etc/eos-companion-app/config.ini`

The presence of one of those files takes complete priority over the others.
For instance, if a user had explicitly enabled the Companion App Services
through the use of the file in /etc, a later ostree update to turn it off by
default in /usr would have no effect.

This file is checked on every boot by a binary written in C for minimal
overhead. That binary is called `eos-companion-app-configuration-manager`,
installed to `@libexecdir@`.

The binary does two file based checks every time it runs:

1. It checks the `config.ini` file in priority order for the enabled key in the
   "Companion App" section (boolean value).
2. It checks for the presence of the `companion-app.service` file in
   `/etc/avahi/services`.

If the `config.ini` file indicates that the Companion App Service is to be
enabled and the `companion-app.service` file does not exist, then a call is made
on dbus on the name `com.endlessm.CompanionAppServiceAvahiHelper` at the object
path `/com/endlessm/CompanionAppServiceAvahiHelper` to
`com.endlessm.CompanionApp.AvahiHelper.EnterDiscoverableMode`

If the `config.ini` file indicates that the Companion App Service is to be
disabled and the `companion-app.service` file exists, then a call is made on
dbus on the name `com.endlessm.CompanionAppServiceAvahiHelper` at the object
path `/com/endlessm/CompanionAppServiceAvahiHelper` to
`com.endlessm.CompanionApp.AvahiHelper.ExitDiscoverableMode`

### Compatibility
If the Companion App Service naively were to link to the SDK directly to
access content, that would limit it to querying content from apps compatible
with that SDK. This isn’t a desirable outcome, because it isn’t guaranteed
that all apps will be ported to newer SDKs.

In order to avoid this outcome in other areas throughout the OS, we have a set
of "eks-search-provider" binaries for each SDK compatibility range (for
instance, v1 is compatible with SDK1, v2 is compatible with SDK2 and SDK3, v3
is compatible with SDK4).

In reality, apps now talk to the same daemon which dynamically "becomes" the
correct eks-search-provider binary and SDK combination depending on which one
was requested. (See:
[EknServicesMultiplexer](https://github.com/endlessm/eos-knowledge-services/docs/Architecture.md)
It is still the caller’s responsibility to work out which
`com.endlessm.EknServices*.SearchProviderV*` interface to use. In the case of
the Companion App, this is done by introspecting the flatpak metadata for the
apps runtime version.

