EOS Companion App  | Content Flow

# Introduction

This document is the technical reference for the Content Flow in the [Companion App](/README.md).
It describes the process and payloads that the client and server should expect
when both the companion app and an Endless Computer acting as a server
transmit content from the Computer to the client device.

# Purpose

The purpose of the content flow is to provide a stable API to transmit content
and metadata to the client device from the Computer, where the content in
question is within the device’s authorization domain. Use cases of this API
include:

1. Listing all available content applications installed on an Endless
   Computer.
2. Viewing HTML, Video and Image content on the device.
3. Requesting supplementary Video and Image content to embed inside of HTML
   content already displayed on the device.
4. Requesting metadata about individual content pieces so as to display that
   metadata or use it internally within the Companion App.
5. Requesting metadata about all the content within a content application.

# Assumptions

1. Both devices are on the same subnet.
2. Endless Computer is running an HTTP server with a domain accessible by
   anyone on the network.
3. The Endless Computer is discoverable by the mobile device using mDNS.

# Flow

## Requesting a Listing of Applications on the Computer
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    GET hostname:port/v2/list_applications?deviceUUID=[a device specific ID]
    Accept: application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "deviceUUID": [unique device ID]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

The following payload should be returned:

    200
    Content-Type: application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    {

        "status": [“ok” or “error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }],
        "payload": [
            {
                "applicationId": [machine-readable application identifier],
                "displayName": [human-readable application name],
                "shortDescription": [Human readable localized application description]
                "icon": [url to icon resource],
                "language": [an RFC5645 encoded language identifier]
            }
            ...
        ]
    }

If the Endless Computer responds with "status": “ok”, the content listed in
the “payload” section should be listed on the device. If the Endless Computer
responds with “status”: “error”, appropriate action should be taken by the
device.

## Requesting Application Icons from Endless Computer
Device sends the following HTTP Payload to the Endless Computer host specified over mDNS

    GET hostname:port/v2/application_icon?iconName=[machine readable icon name]&deviceUUID=[a device specific ID]&size=[machine readable requested icon size]
    Accept: image/png, application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of the URL:

    "iconName": [machine readable icon name, returned by /v2/list_applications],
    "deviceUUID": [unique device ID]

The following URL query-string encoded parameters may appear on the end of the URL

    "size": [machine readable requested icon size, integer]

If the "size" parameter is specified, the service will attempt to provide an
icon with the closest square geometrical size available to the request size.
The service does not guarantee that the returned icon is of the requested
size, nor does it guarantee that the returned icon’s size will be within some
range of the requested size. The client must deal with whatever icon size it
receives.

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

The device must specify both image/png and application/json as part of its Accept header.

The following payload should be returned:

    200
    Content-Type: image/png OR application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    [binary png data]

In the event of an error, the following payload should be returned

    200
    Content-Type: application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": “error”,
        "error": {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }
    }

## Requesting Application Theme Colors from Endless Computer
Device sends the following HTTP Payload to the Endless Computer host specified over mDNS

    GET hostname:port/v2/application_colors?applicationId=[machine readable application ID]&deviceUUID=[a device specific ID]
    Accept: application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of the URL:

    "applicationId": [machine readable application ID, returned by /v2/list_applications],
    "deviceUUID": [unique device ID]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

The device must specify both image/png and application/json as part of its Accept header.

The following payload should be returned:

    200
    Content-Type: application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    {
        "status": [“error” or “ok”],
        [case "status" == “error” “error”: {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }],
        [case "status" == “ok” “payload”: {
            "colors": [array of web-color formatted strings, eg “#00ff00”]
        }]
    }

## Requesting a Category Listing for an Application on the Computer
Device sends the following HTTP Payload to the Endless Computer host specified over mDNS

    GET hostname:port/v2/list_application_sets?applicationId=[machine readable application ID]&deviceUUID=[a device specific ID]
    Accept: application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "applicationId": [machine readable application ID, returned by /v2/list_applications],
    "deviceUUID": [unique device ID]

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

If the specified application ID does not refer to an application on the
Endless Computer, an (EOS_COMPANION_APP, APPLICATION_NOT_FOUND) error will be
returned.

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

The following payload should be returned:

    200
    Content-Type: application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": [“ok” or “error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }],
        "payload": {
            "colors": [list of machine readable web-style color strings],
            "sets": [
            {
                "global": [boolean, whether set is the global set],
                "tags": [semicolon separated list of tags],
                "title": [human readable set name],
                "contentType": [machine-readable MIME type, always “application/x-ekncontent-set”],
                "thumbnail": [relative url to article thumbnail] | null,
                "id": [a machine-readable content-ID, used for querying metadata]
            }
            ...
            ]
        }
    }

If the Endless Computer responds with "status": “ok”, the sets listed in the
“payload” section should be listed on the device by “name”. Content in the
toplevel view could be any of any MIME type, but it will only be “toplevel”
content and not necessarily things like embedded images. The device should
keep note of the “ID” of each piece of content, as it is how an individual
piece of content will be requested later. If the Endless Computer responds
with “status”: “error”, appropriate action should be taken by the device.

If a set has the "global" key set to true, then the set is considered to be a
“global” set and receives special treatment. In particular, it should not be
shown to the user and the device should immediately request the set contents
using the given tags. If a set is marked as “global”, it is guaranteed that it
will be the only set in the response.

If the client application needs to display the name of a set, it should use
the "title" entry in the payload, as opposed to the “tags”. “tags” are
guaranteed to be human readable in all cases, nor are they localized.

## Requesting a Content Listing for Tags for an Application on the Computer
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    GET hostname:port/v2/list_application_content_for_tags?applicationId=[machine readable application ID]&deviceUUID=[a device specific ID]&tags=[semicolon separated list of tags, see below]
    Accept: application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "applicationId": [machine readable application ID,
                      returned by /v2/list_applications],
    "tags": [machine readable list of tags,
             returned as the “tags” parameter in /v2/list_application_sets]
    "deviceUUID": [unique device ID]

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

If the specified application ID does not refer to an application on the
Endless Computer, an (EOS_COMPANION_APP, APPLICATION_NOT_FOUND) error will be
returned.

If none of the specified tags refers to a tag of the any content item for that
application on the Endless Computer, an empty array will be returned. There is
no way to determine if a tag does or does not exist.

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

The following payload should be returned:

    200
    Content-Type: application/json
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": [“ok” or “error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }],
        "payload": [
            {
                "displayName": [human-readable content piece name],
                "contentType": [machine-readable MIME type],
                "thumbnail": [relative url to article thumbnail] | null,
                "id": [a machine-readable content-ID],
                "tags": [machine-readable content tags]
            }
            ...
        ]
    }

If the Endless Computer responds with "status": “ok”, the content listed in
the “payload” section should be listed on the device by “name”. Content in the
toplevel view could be any of any MIME type, but it will only be “toplevel”
content and not necessarily things like embedded images. The device should
keep note of the “ID” of each piece of content, as it is how an individual
piece of content will be requested later. If the Endless Computer responds
with “status”: “error”, appropriate action should be taken by the device.

## Requesting Content Metadata for an Application on the Computer
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    GET hostname:port/v2/content_metadata?applicationId=[machine readable application ID]&contentId=[machine readable content ID]&deviceUUID=[a device specific ID]
    Accept: application/json
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "applicationId": [machine readable application ID, returned by /v2/list_applications],
    "contentId": [machine readable content ID, returned by /list_application_content],
    "deviceUUID": [unique device ID]

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

If the specified "applicationId" does not refer to an application on the
Endless Computer, an (EOS_COMPANION_APP, APPLICATION_NOT_FOUND) error will be
returned.

If the specified "contentId" does not refer to content piece for a shard for
an application on the Endless Computer, an (EOS_COMPANION_APP,
CONTENT_NOT_FOUND) error will be returned.

The following payload should be returned:

    200
    Content-Type: application/json
    ---
    {
        "status": [“ok” or “error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional
                       context behind the error]
        }],
        "payload": {
            "version": “2”
            "contentType": [machine-readable MIME type],
            "license": [machine and human readable license name],
            "copyrightHolder": [optional, human readable name of person who
                                owns the copyright for this resource],
            "height": [optional, integer value specifying the height in pixels
                       for a corresponding image],
            "width": [optional, integer value specifying the width in
                     pixels for a corresponding image],
            "caption": [optional, human readable summary of image],
            "title": [human readable content title],
            "sourceName": [human readable article
                           source name (eg, Wikipedia, WikiHow)],
            "tags ": [
                [machine-readable string indicating the tags for this article]
                ...
            ],
            "matchingLinks": [
                [URI specifying where on the web the article can be located]
                ...
            ],
            "tableOfContents": [
                {
                    "@id": [machine-readable anchor identifier],
                    "hasLabel": [human-readable label for this entry
                                 in the Table of Contents],
                    "hasIndexLabel": [human readable label for where this entry is
                                      indexed in the Table of Contents, eg, 2.3.1]
                    "hasIndex": [integer, indicating the ordering of this
                                 Table of Contents entry relative to others]
                    "hasContent": [machine-readable anchor name]
                }
                ...
            ],
            "thumbnail": [a relative URI to the device host specifying where
                          the Article Thumbnail can be accessed],
            "source": [machine-readable source name],
            "synopsis": [human readable article summary, UTF-8 encoded],
            "originalURI": [machine-readable URI specifying where
                            the article was sourced from],
            "outgoingLinks": [
                [machine-readable URI specifying an a web
                 location for an outgoing link]
                ...
            ],
            "featured": [bool, whether the article is “featured” in the application],
            "@id": [machine-readable content id],
            "@type": [machine-readable article type],
            "resources": [machine-readable list of URIs specifying
                          the resources in use by this article]
        }
    }

If the Endless Computer responds with "status": “ok”, the device may do what
it wishes with the JSON object specified in “payload”.

## Requesting Content Data for an Application on the Computer
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    GET hostname:port/v2/content_data?applicationId=[machine readable application ID]&contentId=[machine readable content ID]&deviceUUID=[a device specific ID]
    Accept: "application/json, [expected content type]"
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "applicationId": [machine readable application ID, returned by /v2/list_applications],
    "contentId": [machine readable content ID, returned by /list_application_content],
    "deviceUUID": [unique device ID]

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

The "Accept" header MUST contain “application/json” and SHOULD contain the
content type expected to be returned by the request, as specified by
/list_application_content

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

If the "Accept" header specifying at least “application/json” is missing from
the request headers, the return status will be 400.

If the specified "applicationId" does not refer to an application on the
Endless Computer, an (EOS_COMPANION_APP, APPLICATION_NOT_FOUND) error will be
returned.

If the specified "contentId" does not refer to content piece for a shard for
an application on the Endless Computer, an (EOS_COMPANION_APP,
CONTENT_NOT_FOUND) error will be returned.

The following payload should be returned:

    200
    Content-Type: [expected content type or "application/json" in the event of an error]
    Connection: keep-alive
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": [“error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }]
    }

OR [binary payload]

The device MUST be able to handle any "Content-Type" that it specified in its
“Accept” header. In particular, it MUST be able to handle “application/json”
as this is the format in which application domain errors will be communicated.

The content_data endpoint supports [HTTP ranges](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Range),
so the client is permitted to send a Range header, formatted like
Range:bytes=start-end? . The server will, as an example, respond with the
following additional headers in case the Range header is set:

1. Accept-Ranges: bytes
2. Content-Length: 16783740
3. Content-Range: bytes 0-16783739/16783740

## Requesting Internal Resource files on the Computer
In some cases, the server might want to pass a URI for a file on the system to
the Companion App for it to load later. For instance, this might be a
resource:/// style URI or a file:/// URI.

Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    GET hostname:port/v2/resource?uri=[uri encoded host URI]&deviceUUID=[a device specific ID]
    Accept: "application/json, [expected content type]"
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "uri": [uri encoded host URI]

The "Accept" header MUST contain “application/json” and SHOULD contain the
content type expected to be returned by the request, as specified by
/list_application_content

The following URL query-string encoded parameters may appear on the end of the
URL:

    "referrer": [Name of view that the user was on before they accessed
                 this resource, see “Metrics and Referrers”]

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned.
See [Authentication Flow](/API.md#Authentication-Flow).

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

If the "Accept" header specifying at least “application/json” is missing from
the request headers, the return status will be 400.

The following payload should be returned:

    200
    Content-Type: [expected content type or "application/json" in the event of an error]
    Connection: keep-alive
    X-Endless-Alive-For-Further: [number of milliseconds after response completes where
                                  server is guaranteed to be alive, see "Keeping the Server Alive"]
    ---
    {
        "status": [“error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind the error]
        }]
    }

OR [binary payload]

The device MUST be able to handle any "Content-Type" that it specified in its
“Accept” header. In particular, it MUST be able to handle “application/json”
as this is the format in which application domain errors will be communicated.

## Performing Searches for Content
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS:

    GET hostname:port/v2/search_content?applicationId=[machine readable application ID]&tags=[machine readable tags, semicolon delimited]&deviceUUID=[a device specific ID]&limit=[machine readable limit integer]&offset=[machine readable offset integer]&searchTerm=[prefix string]
    Accept: "application/json"
    ---
    null

The following URL query-string encoded parameters MUST appear on the end of
the URL:

    "deviceUUID": [unique device ID]

The following parameters MAY appear at the end of the URL, and will limit the
scope of the search

    "applicationId": [machine readable application ID,
                      returned by /v2/list_applications],
    "tags": [machine readable tags, semicolon delimited,
             returned by /v2/list_application_sets],
    "limit": [machine readable limit integer, default 50],
    "offset": [machine readable offset integer, default 0],
    "searchTerm": [search term, string]

The "Accept" header MUST contain “application/json”.

If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned. See [Authentication Flow](/API.md#Authentication-Flow).

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

If the specified "applicationId" does not refer to an application on the
Endless Computer, an (EOS_COMPANION_APP, APPLICATION_NOT_FOUND) error will be
returned.

The "applicationId", “tags” and "searchTerm" entries limit the scope of the
query. “applicationId” must match an application exactly, or an error will be
returned. “tags” may be a semicolon delimited list of sets a content piece
could belong to (set OR). "searchTerm" is a search term that the content
piece’ “title” property must prefix-match.

At least one of "applicationId", “tags” or “searchTerm” must be specified. If
none of them are specified, an (EOS_COMPANION_APP, INVALID_REQUEST) error will
be returned.

The "limit" and “offset” parameters may be used to paginate the response. The
response will contain at most “limit” entries. The “offset” parameter can be
used to control where the returned list starts from.

The most general use case for this API is to search across all content for a
term. All that needs to be specified in that case is searchTerm and
deviceUUID.

The following payload should be returned:

    200
    Content-Type: "application/json"
    Connection: keep-alive
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": “error” or “ok”,
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding
                       additional context behind the error]
        }],
        "payload": {
            "remaining": [integer, number of content pieces
                          remaining not shown in the search],
            "applications": [
                {
                    "applicationId": [machine-readable app-id for app
                                      whose content was included in “results”],
                    "displayName": [human readable app name for app
                                    included in “results”],
                    "shortDescription": [Human readable localized
                                         application description],
                    "icon": [URL to icon resource for app included in “results”],
                    "language": [an RFC5645 encoded language identifier]
                }
            ],
            "results": [
                {
                    "displayName": [human-readable content piece name],
                    "payload": [one of:
                        case "type" == “content”: {
                            "applicationId": [machine-readable application ID
                                              this content piece pertains to],
                            "contentType": [machine-readable MIME type],
                            "id": [machine readable content-ID],
                            "tags": [machine readable content-tags],
                            "thumbnail": [relative url to content thumbnail] | null,
                        }
                        case "type" == “set”: {
                            "applicationId": [machine-readable application ID this
                                              content piece pertains to],
                            "tags": [machine readable set-tags],
                            "thumbnail": [relative url to set thumbnail] | null
                        },
                        case "type" == “application”: {
                            "applicationId": [machine-readable application ID
                                              entry pertains to]
                        }
                    ],
                    "type": [one of “set”, “content” or “application”]
                }
            ]
        }
    }

The returned "type" indicates whether the entry should take the user to the
content itself, to a set listing additional content or to the sets for an
application. It also determines the structure of the “payload” attribute.

In the case that "type" is “content”, it will have a corresponding
“applicationId”, which can be looked up in the “applications” list for details
like the application name and icon, a “contentType”, similar to that used in
/list_application_content_for_set, “tags” and a thumbnail URI.

In the case that "type" is “set”, it will have a corresponding
“applicationId”, which can be looked up in the “applications” list for details
like the application name and icon, “tags” which should be used to list the
contents of the set through list_application_content_for_tags and a
“thumbnail” URI.

If then type is "application", only the “applicationId” will be provided;
further details like the application name and icon can be looked up in the
“applications” list.

The "remaining" entry indicates how many content pieces were not shown in the
search. This can be used for pagination.

## Requesting a Content Feed
A device may request a "feed" of content to be displayed, similar to the
Facebook or Instagram news feeds. The news feed is made up of content entries,
each having a potentially different type and properties, as outlined in this
section.

In order to support "infinite" scrolling and pagination, the server will
communicate both the feed itself and a server-state of what content entries
are in the feed. The client will receive the details of this state, which can
be communicated back to the server in order to fetch more entries to append to
the end of the feed.

Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS:

    GET hostname:port/feed?deviceUUID=[machine readable device UUID]&mode=[machine readable whether content should be appended/prepended]&lastServerState=[url encoded JSON starting point state]&limit=[machine readable limit integer]
    Accept: "application/json"
    ---
    null

The following URL query-string encoded parameters MUST appear at the end of
the URL:

    "deviceUUID": [unique device ID],
    "mode": [“append” or “prepend”]

The following parameters MAY appear at the end of the URL, and will control
which entries are returned by the feed.

    "lastServerState": [URL-encoded JSON feed state from last request],
    "limit": [maximum number of entries to return],

If "lastServerState" is not specified, entries from the “top” of the feed will
be returned. The number of new entries returned is limited by “limit”, though
that is not the lower bound. Fewer entries may be returned, though this is not
necessarily indicative that there are no more entries left to return. The only
true indication that this is the case is if a query is made with the last
returned state as “lastServerState” and the “hasNewerEntries” field is set to
false. For the avoidance of doubt, “limit” is not the absolute limit of
entries that will be returned in a request. This could be any number. It only
limits the number of **new** entries in the returned feed.

If pulling down from the top of the feed, mode MUST be "prepend" and
“lastServerState” should generally be set. The server will try to prepend new
content and may mix in old content depending on what the last state was.

If scrolling down to the bottom, mode MUST be set to "append" and
“lastServerState” should generally be set if it is available. The server will
try to append older content depending on what the last state was.

In both cases, the entire feed will be returned. It is assumed that the server
will always return what was in the feed beforehand, so the feed can be cleared
and re-constructed from scratch. In a future API revision, the server may
support sending deltas of content.

Upon successful invocation, the following payload should be returned:

    200
    Content-Type: "application/json"
    Connection: keep-alive
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    ---
    {
        "status": “error” or “success”,
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding
                       additional context behind the error]
        }],
        "payload": [null or {
            "state": {
                "sources": [
                    {
                        "source": {
                            "type": [one of “application”],
                            "detail": [
                                case type == "application": {
                                    "applicationId": [machine-readable application ID]
                                }
                            ]
                        },
                        "itemType": [“news”, “article”, “video”,
                                     “artwork”, “wordOfTheDay”, “quoteOfTheDay”],
                        "endpointMarker": [any datatype, machine-readable identifier
                                           acting as a key for the very last content entry
                                           shown in this collection]
                    },
                ],
                "index": [machine readable integer type]
            },
            "sources": [
                {
                    "type": [“application”],
                    "detail": [
                        case type == "application": {
                            "applicationId": [machine-readable application ID],
                            "icon": [URI to icon image],
                            "displayName": [Human readable localized application name],
                            "shortDescription": [Human readable localized
                                                 application description]
                        }
                    ]
                }
            ],
            "entries": [
                {
                    "itemType": [“news”, “article”, “video”,
                                 “artwork”, “wordOfTheDay”, “quoteOfTheDay”],
                    "source": {
                        "type": [“application”],
                        "detail": [
                            case type == "application": {
                                "applicationId": [machine-readable application ID]
                            }
                        ]
                    },
                    "detail": [
                        case itemType == "news": {
                            "title": [Human readable item title, not the
                                      same as the source name],
                            "synopsis": [Human readable summary, 2 to 3 lines],
                            "thumbnail": [Machine readable URI to thumbnail],
                            "uri": [URI to article content],
                            "contentType": [machine readable MIME type
                                            for underlying content]
                        },
                        case itemType == "article": {
                            "title": [Human readable item title, not the
                                      same as the source name],
                            "synopsis": [Human readable summary, 2 to 3 lines],
                            "thumbnail": [Machine readable URI to thumbnail],
                            "uri": [URI to article content],
                            "contentType": [machine readable MIME type
                                            for underlying content]
                        },
                        case itemType == "video": {
                            "title": [Human readable item title, not the
                                      same as the source name],
                            "thumbnail": [Machine readable URI to thumbnail],
                            "uri": [URI to article content],
                            "duration": [Machine readable clip duration],
                            "contentType": [machine readable MIME type
                                            for underlying content]
                        },
                        case itemType == "artwork": {
                            "title": [Human readable item title, not the
                                      same as the source name],
                            "author": [Human readable author name, used for byline],
                            "firstDate": [Machine readable date of first publication],
                            "thumbnail": [Machine readable URI to thumbnail],
                            "uri": [URI to article content],
                            "contentType": [machine readable MIME type
                                            for underlying content]
                        },
                        case itemType == "wordOfTheDay": {
                            "word": [Human readable item title, not the
                                     same as the source name],
                            "partOfSpeech": [Human readable part of speech],
                            "definition": [Human readable definition]
                        }
                        case itemType == "quoteOfTheDay": {
                            "quote": [Human readable contents of the quote],
                            "author": [Human readable author name,
                                       including lifespan period]
                        }
                    ]
                }
            ],
            "numberNewEntries": [number of new entries returned in this request],
        }
    }]

### The "state" entry
The "state" entry is documented, but is not really intended to be parsed by
the device and its contents should be considered unstable. It should be
stringified as JSON and sent back URI-encoded to the server whenever a request
for additional content is made by scrolling to the end of the feed. For
instance, if the “state” key for the last feed response contained:

    "state": {
        "sources": [
            {
                "source": {
                    "type": “application”,
                    "detail": {
                        "applicationId": “com.endlessm.animals.en”
                    }
                },
                "itemType": “Article”,
                "endpointMarker": 2
            }
        ],
        "index": 15
    }

This stringifies to:

    {"sources": [{"source":{"type":"application","detail":{"applicationId":"com.endlessm.animals.en"}},"itemType":"Article","endpointMarker":2}],“index”:15]

Which, as URL-encoded, is:

    %7B%E2%80%9Csources%E2%80%9D%3A%20%5B%7B%22source%22%3A%7B%22type%22%3A%22application%22%2C%22detail%22%3A%7B%22applicationId%22%3A%22com.endlessm.animals.en%22%7D%7D%2C%itemType%22%3A%22Article%22%2C%22endpointMarker%22%3A2%7D%5D%2C%E2%80%9Cindex%E2%80%9D%3A15%5D

This payload should be passed directly to the "lastServerState" query string
value on a subsequent request for more content. If more content is required
past that point, the “state” key of the new payload should be used, as above.

On the server side, the URI encoded lastServerState is URI-decoded and then
deserialized from JSON. In essence, it tells the server what offsets to use
when querying databases for subsequent content. In this example, we already
fetched and displayed 2 Articles with content from the com.endlessm.animals.en
app source (the "endpointMarker") and are “up to” index 15.

The index itself is used to figure out what offset to use into the view of an
"infinite" feed that would be built up on the server side. Obviously, the full
feed is not built up, but one could imagine that N content entries may be
allocated per day, such that index % N = D specifies which day to query from
(where D is Today - D days).

Note that the index is not necessarily representative of how many entries have
actually been returned by the service so far, but rather it is an indicator as
to which point to start from on the next scroll action. For instance, the
ordering algorithm on the service side might require that a quota of N entries
is filled per day. If we can’t fill that many entries, obviously we would want
the next request to start from the next day as opposed to trying to get the
next N - M entries from the current day in futility. The best way for this to
happen is for the server to send back the number of slots it expected to fill
in the request and for the client to treat this as the current index when it
responds by just sending back the stringified state in the request.

### The "sources" entry
The "sources" entry holds information about each source. It is hoisted to be a
part of its own entry so that we can refer to sources by their key-value
(e.g., an application ID) and then look up things like icons and display names
from one place as opposed to encoding it in every entry.

For now, the only sources are "applications". However, there could be other
types of sources as well going forward (think social, etc).

### The "entries" entry
This is where the actual content behind the feed is stored.

Each entry has a "source", which has a type and a “detail” parameter. Each
source type is guaranteed to have some key or set of keys in its “detail” that
can be used to look up the corresponding source detail in the “sources” entry.
Generally speaking, the “source” and its corresponding detail might be used to
display the header of a card (for instance “Animals”, or “Word of the Day” or
even the name of a person if the source was a social post of some kind).

Each entry also has a "itemType" which specifies what properties the entry
will have and how it should be rendered. Note that some “itemType”s might have
identical property sets, but they still have a different entry type because
they should be rendered slightly differently.

In general, the following content types are in use:

1. News: Used for Time-Sensitive News Articles. "title" is the news article
   title and “synopsis” is the first few lines of the article. “thumbnail” is
   a URI specifying a thumbnail image to display alongside the headline and
   synopsis. When the card is pressed by the user, the “uri” should be
   activated and the user should navigate there.
2. Article: Used for Non-Time-Sensitive Content Articles. "title" is the news
   article title and “synopsis” is the first few lines of the article.
   “thumbnail” is a URI specifying a thumbnail image to display alongside the
   headline and synopsis. When the card is pressed by the user, the “uri”
   should be activated and the user should navigate there.
3. Video: Used for articles that embed videos. The "thumbnail" is a URI to a
   still of the video, but a play button should be rendered on top to indicate
   to the user that the content is a video. “title” is just the title of the
   video. The “duration” entry should be formatted as a single integer
   specifying the number of seconds long the video is. This should be
   displayed to the user in HH:MM:SS format.
4. Artwork: Used for articles discussing noteworthy images (currently only
   WikiArt). The "title" entry is the name of the artwork. The “author” entry
   is the author of the work (which is difficult from the author of the
   article itself) and should be displayed alongside the title of the work in
   a slightly larger font than would be used for the synopsis. The “firstDate”
   property is the first known publication date. This is the earliest date out
   of all dates if the publication has a range of possible publication times.
   The “thumbnail” is just a URI to an image of the artwork itself and the
   “uri” is a link to the WikiArt Application’s content page for that artwork.
5. WordOfTheDay: Used for articles discussing words in the dictionary
   (currently only com.endlessm.word_of_the_day). The "word" entry is the word
   itself. The “partOfSpeech” entry is the part of speech (eg, noun, verb) for
   that word. The “definition” is a 2-3 line definition of that word. Note
   that there is no “url” property here, nor a “thumbnail” and the card is not
   clickable.
6. QuoteOfTheDay: Used for articles discussing noteworthy quotes in the
   dictionary (currently only com.endlessm.quote_of_the_day). The "quote"
   entry is the quote itself, limited to 1-2 lines. The “author” entry is the
   person who said that quote, including their lifespan. Note that there is no
   “url” property here, nor a “thumbnail” and the card is not clickable.

### Error Handling
If the Device UUID specified in the query string is not a member of the
authorized devices list to perform this action, an (EOS_COMPANION_APP,
DEVICE_NOT_AUTHORIZED) error will be returned. See [Authentication Flow](/API.md#Authentication-Flow).

If a query-string encoded parameter is missing from the request, an
(EOS_COMPANION_APP, INVALID_REQUEST) error will be returned.

If the server cannot make sense of the returned URI encoded lastServerState,
then (EOS_COMPANION_APP, INVALID_STATE) will be returned.

# URL Rewriting and Embedded Content
Returned content may contain rewritten links. The server running on the
Endless computer GUARANTEES that they are ALWAYS resolvable so long as the
server is running and a connection to the Endless Computer can be established.
The rewritten URL will always be relative to the host of the Endless Computer
from which the content was accessed. The rewritten URL will also contain the
deviceUUID parameter, the client does not need to add it again themselves.

The server does not guarantee that the content will always be accessible - the
content in question may be restricted by authorization policy.

The server does not guarantee that any rewritten URL loaded from another
Endless Computer will be resolvable or even valid, they are only valid for the
computer they were initially loaded from.

URLs contained within JSON responses will not automatically include the
deviceUUID parameter, this must be added by the device itself. As an
exception, URLs rewritten and included in returned content will include the
deviceUUID parameter, since this greatly simplifies the implementation on the
client side.

# Legacy Service API versioning
Versions of the App and the Service featuring different API revisions may be
deployed concurrently and interact with each other. The App and the Service
should thus have a mechanism in order to prevent unexpected behaviour due to
version mismatches.

At present, multiple concurrent deployments of the App and the Service should
be considered incompatible and not used together. The canonical way of
handling such mismatches is for the client to check the service’ API version
against the client’s API version and do the following if the versions are not
equal:

* If the client’s version is greater, error out with a message that the
  ‘Endless Platform’ package on the Endless Computer needs to be upgraded from
  the App Center.
* If the server’s version is greater, error out with a message that the
  ‘Endless Companion’ App needs to be upgraded on Google Play.

In general, distributors of both the App and the server should be careful to
avoid shipping incompatible App and Service versions as the most up to date
version.

In order to transition towards supporting concurrent service versions in the
future, all routes are prefixed with /v1/. The version number in this route is
generally not bumped, but may be in the future.

To request the service version, the App should use the following HTTP GET request.

    GET hostname:port/version
    Accept: "application/json"
    ---
    null

The server will respond with:

    200
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    Content-Type: application/json
    ---
    {
        "status": “ok”,
        "payload": {
            "version": [Integer indicating server API version]
        }
    }

Unfortunately, such an approach unintentionally imposed a requirement that app
and service versions be updated in lockstep. As such this approach will be
retired at version 3 in favour of "Supported Versions" below.

# Concurrent Service API versioning
Versions of the App and the Service featuring different API revisions may be
deployed concurrently and interact with each other. The App and the Service
should thus have a mechanism in order to prevent unexpected behaviour due to
version incompatibilities.

At present, multiple concurrent deployments of the App and the Service may be
considered incompatible and not used together. The canonical way of handling
such mismatches is for the client to check the service’ supported route API
versions against the client’s API version and do the following if the version
is not contained in the list returned by the server:

* If the client’s version is greater than any version in the list, error out
  with a message that the ‘Endless Platform’ package on the Endless Computer
  needs to be upgraded from the App Center.
* If the server’s version is less than any version in the list, error out with
  a message that the ‘Endless Companion’ App needs to be upgraded on Google
  Play.

In general, distributors of both the App and the server should be careful to
avoid shipping incompatible App and Service versions as the most up to date
version.

The returned list of versions returned by the server are all of the /vX route
prefixes supported. For instance, if the server claims to support versions [1, 2, 3]
then any app using routes beginning with /v1, /v2 or /v3 is supported. The
server also guarantees that the list of supported versions will be ordered
contiguous integers, such that there are no "gaps" in the supported versions.

In order to transition towards supporting concurrent service versions in the
future, all routes are prefixed with /v1/. The version number in this route is
generally not bumped, but may be in the future.

To request the supported service route versions, the App should use the
following HTTP GET request.

GET hostname:port/supported_route_versions
Accept: "application/json"
null
---
The server will respond with:

    200
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    Content-Type: application/json
    --
    {
        "status": “ok”,
        "payload": {
            "versions": [Contiguous ordered list of integers
                         indicating supported server API versions]
        }
    }

This approach replaces "Legacy Service API Versioning" above from legacy
server API version 3.

# Metrics and Referrers
The server may optionally append a referrer= querystring argument to the end
of any request. This will be recorded by the metrics system to determine where
the user came from when they accessed a given URL in the app.

In generally, the referrer attribute should uniquely identify the location of
the view that the user was in. Generally speaking this is one of:

* feed
* search_content
* list_application_content_for_tags
* list_applications
* list_application_sets
* device_authenticate
* refresh
* retry
* back
* content

If more referrers are to be added, the general principle is to be liberal with
adding more types of referrers, but use them consistently.

# Keeping the Server Alive
Since the Companion App Server runs on consumer hardware, without
intervention, the user’s power management policy will activate, putting the
machine into S3 and interrupting the connection. When the service is in S3 it
will be unreachable both by TCP/IP and will not be discoverable on mDNS.

To mitigate this, the server guarantees that upon responding to a request, the
system will not go to sleep, unless explicitly requested by a user action, up
until when the number of milliseconds specified. That time point is a 64-bit
number of milliseconds after the response completes where server is guaranteed
to be alive contained in the X-Endless-Alive-For-Further: header, which shall
be included every response.

If the client needs to extend the deadline, it should make the following
request to the server before the time specified in the
X-Endless-Alive-For-Further header.

    POST /heartbeat
    --
    null

The server will always respond as follows:

    200
    X-Endless-Alive-For-Further: [number of milliseconds after response
                                  completes where server is guaranteed to be
                                  alive, see "Keeping the Server Alive"]
    Content-Type: application/json
    --
    { "status": “ok” }

By default, making any request to the server will extend the deadline to five
minutes after the current time, though this should not be relied on. The
client should instead use the value of the X-Endless-Alive-For-Further header
to determine when to send the next /heartbeat, taking into account the fact
that the server is only guaranteed to be alive up until that deadline and that
network latency may necessitate sending requests before the deadline expires.

# Error Codes
Error payloads may have a "domain", “code” and “detail” sub-object. The
“domain” and “code” are mandatory for an error payload to be well-formed. The
“domain” specifies where in the stack the error originated from (IO, from the
App itself, networking, third party library exception). The “code” specifies
what error actually occurred with granular enough detail such that both the
device and the Endless Computer can decide what to do with the error. Errors
may optionally include a “detail” key with a JSON object specifying additional
details that can be used in an error message for the user. Importantly, error
message should NOT include any localized strings since we cannot guarantee
what locale the device and the computer will be running with. Instead expected
errors should be deserialized on either either end of communication and an
error message in the appropriate locale shown.

## EOS_COMPANION_APP

This is the domain for all errors originating from the app itself and not from
libraries further down the stack.

INVALID_REQUEST: Programmer error. Device did not include something in the
                 request that the server expected.
DEVICE_NOT_AUTHORIZED: Device is not authorized to access content on this computer.
                       Authentication flow should be performed again if this error
                       is hit when requesting content.
CONTENT_NOT_AUTHORIZED: Device is not authorized to access this piece of
                        content.
APPLICATION_NOT_FOUND: Application does not exist.
CONTENT_NOT_FOUND: Content does not exist for shard for application.
INVALID_STATE: Client sent back a server-encoded state that
               did not make any sense.
INVALID_STATE: Request was cancelled by the client or server.
