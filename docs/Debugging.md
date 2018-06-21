# Debugging Guide for Companion App Service
This is a small, non-comprehensive guide to debugging the
Companion App Service. Since the service itself is quite
deeply [integrated](/docs/OSIntegration.md) into the rest
of Endless OS, debugging it can be painful, but it is
possible.

## Checking the logs for errors
Since the Companion App Service runs by default as a
systemd unit, you can check the system logs in case anything
goes wrong by using `journalctl | grep CompanionAppService`.

    Jun 16 23:45:49 endless dbus-run-session[30441]: CompanionAppService INFO: Got session d-bus connection at /com/endlessm/CompanionAppService
    Jun 16 23:45:49 endless dbus-run-session[30441]: CompanionAppService INFO: Got system d-bus connection

## Running without Socket Activation
If you need to quickly iterate on a problem, or interactively
debug the Service, you'll need to run the flatpak directly. However,
it isn't possible to just `flatpak run com.endlessm.CompanionAppService`
right away since systemd will be listening on port 1110 in order
to socket-activate the Service.

In order to resolve this problem, you'll need to disable
socket activation. If you just want to do that for the
current boot, use `systemctl stop eos-companion-app.service`
(stops any running services) and
`systemctl stop eos-companion-app.socket` (stops systemd
from listening on port 1110 if the service is not running). To
prevent it from running on further reboots, then in addition
to the above two, use `systemctl disable eos-companion-app.socket`,
which will remove the socket unit from the default boot path.

After that you can use `flatpak run com.endlessm.CompanionAppService`
to run the service as your own user. Note that the Service will
automatically shut down after 15 seconds of receiving no activity
and 5 minutes after the last network activity, so you may need
to restart it from time to time.

If you want to interactively debug it, you'll need to enter
a shell in the sandbox with the development tools and debuginfo
runtimes mounted. You can do that with:

    $ flatpak run --devel --command=/bin/bash com.endlessm.CompanionAppService
    $ gdb --args python3 $(which eos-companion-app-service)

## Replicating the Socket Activation environment interactively
Sometimes the bug might not be reproducible when the Companion
App Service is being run as a regular user, possible because
it has access to a something that it wouldn't have access to
when running as the more tightly sandboxed `companion-app-helper`
user (for instance, files in the home directory layout,
access to D-Bus services running on the user's session bus).

In these cases, it will be necessary to run the Companion
App Service in a similar environment to what gets run during
socket activation. It isn't possible to replicate this
environment completely, but you can get close to it.

First, switch to the `companion-app-helper` user:

    $ sudo -u companion-app-helper /bin/bash
    companion-app-helper@endless$

Next, run a private session bus:

    companion-app-helper@endless$ dbus-run-session /bin/bash
    companion-app-helper@endless$ echo $DBUS_SESSION_BUS_ADDRESS
    unix:abstract=/tmp/dbus-gVZmDmjMR2,guid=c5e42c9e4f8ae261a39911c25b253a36

You'll need to set HOME as well

    companion-app-helper@endless$ cd /var/lib/eos-companion-app
    companion-app-helper@endless$ export HOME=$(pwd)

Then, set XDG_RUNTIME_DIR and XDG_DATA_DIRS:

    companion-app-helper@endless$ export XDG_RUNTIME_DIR=/tmp/run
    companion-app-helper@endless$ export XDG_DATA_DIRS=/var/lib/flatpak/exports/share:/var/endless-extra/flatpak/exports/share

Now run the Companion App Service, but disable the documents
portal and the a11y bus:

    companion-app-helper@endless$ flatpak run --no-a11y-bus --no-documents-portal --no-desktop com.endlessm.CompanionAppService

The Companion App Service will run as the companion-app-helper
on its own private session bus, separate from your user's
session bus. If it needs to talk to any services
such as `EknServices`, the private session bus will spawn
them as required.

### Debugging EknServices on the private session bus
You may be unfortunate enough to have the problem happen
within EknServices while it is only running on a private
session bus for the companion-app-helper user. If that is
the case, you'll need to debug EknServices while it is
connected to the same private session bus.

First, take note of the fact that EknServices on Endless OS
is shipped through a flatpak called EknServicesMultiplexer. This
flatpak does some tricks which allow multiple versions of
EknServices to co-exist in the same package, however it does
not ship with any debugging symbols. You'll need to
install the relevant EknServices version directly, which
will "supercede" whatever is in the multiplexer. For example:

    $ flatpak install eos-sdk com.endlessm.apps.Sdk//3
    $ flatpak install eos-sdk com.endlessm.app.Sdk.Debug//3
    $ flatpak install eos-sdk com.endlessm.EknServices3
    $ flatpak install eos-sdk com.endlessm.EknServices3.Debug

After performing the operations above to spawn the
Companion App Service on its own session bus, spawn another
shell and change to the companion-app-helper user, exporting
everything that's needed:

    $ sudo -u companion-app-helper /bin/bash
    companion-app-helper@endless$ cd /var/lib/eos-companion-app 
    companion-app-helper@endless$ export HOME=$(pwd)
    companion-app-helper@endless$ export XDG_RUNTIME_DIR=/tmp/run
    companion-app-helper@endless$ export XDG_DATA_DIRS=/var/lib/flatpak/exports/share:/var/endless-extra/flatpak/exports/share

Now that you've done that, take note of the value of
DBUS_SESSION_BUS_ADDRESS printed earlier and export that to the
same value:

    companion-app-helper@endless$ export DBUS_SESSION_BUS_ADDRESS=unix:abstract=/tmp/dbus-gVZmDmjMR2,guid=c5e42c9e4f8ae261a39911c25b253a36

That will ensure that when when the relevant version of EknServices
is started, it will run on the same session bus as the Companion App
Service and that the Companion App Service will be able to talk to
it.

Now, start debugging the relevant version of EknServices:

    companion-app-helper@endless$ flatpak run --devel --command=/bin/bash com.endlessm.EknServices3
    companion-app-helper@endless$ gdb --args eks-search-provider-v3
    (gdb) r

## Debugging Content Rendering
Content rendering is partly done by the Companion App Service itself
and partly done by the
[eos-knowledge-content-renderer](https://github.com/endlessm/eos-knowledge-content-renderer)
library.

All HTML content is partly renderered by the logic in the Companion
App Service itself, which basically just passes a bunch of strings
(including the HTML) to be substituted into a
[mustache template](/data/templates/mobile-article-wrapper.mst).

"Legacy" content (articles scraped from Wikipedia, WikiHow, WikiSource
and WikiBooks) are rendered by the `eknr_renderer_render_legacy_content`
function. This should be comprehensively tested by its corresponding
[test suite in the Knowledge Framework](https://github.com/endlessm/eos-knowledge-lib/blob/master/tests/js/framework/testArticleHTMLRenderer.js).
If you need to iterate on this, it probably makes more sense to build
both eos-knowledge-content-renderer and eos-knowledge-lib into custom
prefix while using a shell in the SDK. For instance:

    $ flatpak run --devel --command=/bin/bash --filesystem=home com.endlessm.apps.Sdk//3
    $ git clone git://github.com/endlessm/eos-knowledge-lib
    $ git clone git://github.com/endlessm/eos-knowledge-content-renderer
    $ export PREFIX=$(pwd)/prefix
    $ export LD_LIBRARY_PATH=$PREFIX/lib
    $ export PKG_CONFIG_PATH=$PREFIX/lib/pkgconfig
    $ export GI_TYPELIB_PATH=$PREFIX/lib/girepository-1.0
    $ pushd eos-knowledge-content-renderer; meson build -Dprefix=$PREFIX; pushd build; ninja && ninja install; popd; popd;
    $ pushd eos-knowledge-lib; ./autogen.sh --prefix=$PREFIX; make && make check; popd;

You can iterate through by making changes to eos-knowledge-content-renderer
and running the tests in eos-knowledge-lib.

### Debugging what rendered content "looks like"
If you need to iterate on a more visual representation of the
content, you can use the browser's developer tools to do that
in conjunction with running the Companion App Service.

First, modify the Flatpak Manifest to look for the renderer
at a particular location on disk and branch:

    {
        "name": "eos-knowledge-content-renderer",
        "buildsystem": "meson",
        "sources": [
            {
                "type": "git",
                "branch": "your-branch"
                "url": "path/to/eos-knowledge-content-renderer
            }
        ]
    }

Then rebuild, reinstall and run the flatpak:

    $ bash build-flatpak.sh
    $ flatpak install com.endlessm.CompanionAppService.flatpak
    $ flatpak run com.endlessm.CompanionAppService

Now, navigate to `http://localhost:1110/v2/list_applications?deviceUUID=test` in
your browser to get a listing of all applications on your computer:

    {  
        "payload":[  
            {  
                "icon":"/v2/application_icon?iconName=com.endlessm.celebrities.id&deviceUUID=foo",
                "language":"id",
                "applicationId":"com.endlessm.celebrities.id",
                "displayName":"Selebritis",
                "shortDescription":"Ketahui lebih banyak tentang selebriti favorit Anda"
            },
        ],
        "status":"ok"
    }

Now, to use the `com.endlessm.celebrities.en` app as an example,
navigate to `http://localhost:1110/v2/list_application_sets?deviceUUID=test&applicationId=com.endlessm.celebrities.en`:

    {  
        "status":"ok",
        "payload":{  
            "colors":[
                ...
            ],
            "sets":[  
                ...
                {  
                    "title":"Musicians",
                    "tags":[  
                        "Musicians"
                    ],
                    "thumbnail":"/v1/content_data?applicationId=com.endlessm.celebrities.en&deviceUUID=foo&contentId=3473e8b450789e0d20e2e9106f8a45767172e3c0",
                    "global":false,
                    "contentType":"application/x-ekncontent-set",
                    "id":"5447363f8c4a1a70f356a919b3b5bd25f3ca2c09"
                }
            ]
        }
    }

We will navigate to "Musicians", so we use
`http://localhost:1110/v2/list_application_content_for_tags?deviceUUID=test&applicationId=com.endlessm.celebrities.en&tags=Musicians`:

    {  
        "payload":[  
            ...
            {  
                "contentType":"text/html",
                "tags":[  
                    "Musicians",
                    "EknArticleObject",
                    "EknHasThumbnail"
                ],
                "thumbnail":"/v1/content_data?contentId=142e2253db44c67178a5835a53a6dcd2cfc2fde1&deviceUUID=foo&applicationId=com.endlessm.celebrities.en",
                "displayName":"John Lennon",
                "id":"561086214c010cba2beb92dedf6740095587e5d2"
            },
            ...
        ],
        "status":"ok"
    }

Finally, we will navigate to the article about John Lennon, which in this
version of the shard, has an ID of `561086214c010cba2beb92dedf6740095587e5d2`. So
we navigate to `/v2/content_data?contentId=561086214c010cba2beb92dedf6740095587e5d2&deviceUUID=foo&applicationId=com.endlessm.celebrities.en`

The page should render directly in the browser. From there, you can inspect
elements, run arbitrary JavaScript or tweak styles until you are satisfied
with the result. To simulate what the page looks like on the phone, most
browsers support a "responsive viewport" mode which allows you to change
the viewport size to the widgets of common devices such as
Samsung Galaxy phones or the iPhone.

## Debugging Feed
Most of the logic for the feed lives in a library called
[libcontentfeed](https://github.com/endlessm/libcontentfeed).

Both the Companion App and Discovery Feed use the same API
calls (`content_feed_find_providers`,
`content_feed_instantiate_proxies_from_discovery_feed_providers`,
`content_feed_unordered_results_from_queries` and
`content_feed_arrange_orderable_models`) to assemble the
feed that gets shown to the user. It is thus far easier
to debug problems happening within libcontentfeed by
debugging the desktop Discovery Feed itself.

You can build a flatpak of the Discovery Feed using
the same `build-flatpak.sh` script. Run the Discovery
Feed with:

    $ DISCOVERY_FEED_DEBUG_WINDOW=1 flatpak run com.endlessm.DiscoveryFeed

## Debugging Tests
If you intend to run the test/lint cycle manually without
having to rebuild the Flatpak all the time,
open `com.endlessm.CompanionAppService.PipDependencies.json`
and remove the `cleanup` section:

    "cleanup": [
        "*"
    ],

Then rebuild the flatpak without running tests and install it:

    $ RUN_TESTS=false bash build-flatpak.sh
    $ flatpak install com.endlessm.CompanionAppService.flatpak

Once installed, you can run the flatpak with the SDK and Debug
runtimes mounted and with local filesystem access to quickly run
the tests or run the linter:

    $ flatpak run --devel --filesystem=$(pwd) --command=/bin/bash com.endlessm.CompanionAppService
    $ python3 -m unittest discover
    $ make pylint

If you need to attach gdb to a crashing test, you can do that
from within the flatpak as run above:

    $ gdb --args python3 -m unittest discover
