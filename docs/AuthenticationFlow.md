# Introduction
This document is the technical reference for how the Authentication Flow
of the Companion App.. It describes the process and payloads that the client
and server should expect when both the companion app and an Endless Computer
acting as a server establish a connection.

# Purpose
The purpose of the authentication flow is to enable reasonably anticipated
future use cases on the server-side without needing to push updates to the
Companion App. Those use cases include (briefly):

1. Limiting which devices can access content on an Endless Computer.
2. Limiting which content a device is permitted to access on an Endless
   Computer.
3. Limiting when a device is permitted to access content.
4. Revoking the ability for a device to access content on an Endless Computer.

All of these use cases can be facilitated by granting permissions to a
non-portable device identifier which is assumed to remain constant throughout
the lifespan of the device.

# What we don’t care about
1. MITM’ing
2. Encryption

# Assumptions
1. Both devices are on the same subnet.
2. Endless Computer is running an HTTP server accessible by anyone on the
network.
3. The Endless Computer is discoverable by the mobile device using mDNS.

# Flow

## Service Discovery
Endless Computer has a "discoverable" mode and places the following record in
the mDNS broadcast when it receives an mDNS packet.

    Name: _eoscompanion._tcp
    Port: 1110
    Host [ip addr]
    txt: ServerUUID=[RFC 4122 uuid]

The ServerUUID field is guaranteed to be unique for that computer and will
remain consistent as long as the Companion App Services are installed on the
computer. The Device may use this UUID as a way of recognising prior servers it
has connected to in the past.

## Authentication request to Endless Computer
Device sends the following HTTP Payload to the Endless Computer host specified
over mDNS

    POST hostname:port/device_authenticate?deviceUUID=[A device-specific unique ID]
    Content-Type: application/json
    Accept: application/json
    ---
    {
        "device_name": [A localized human-readable device name that will be
                        displayed on the Endless Computer, eg “Sam Spilsbury’s
                        Android Phone”]
        "device_description" : [A localized human-readable device description that
                                will be displayed on the Endless Computer, eg “Oppo
                                R4 Smartphone”],
        "request_timeout_ts": ISO8601 timestamp representing the time at which the
                              request is considered to have timed out and should be
                              re-attempted.
    }

The Endless Computer should decide what to do as described in the Endless
Computer Authentication section and then send an HTTP response.

## Endless Computer Authentication

The Endless Computer may decide what to do with the authentication
request, however it should eventually respond to it as specified in the section
below. Two options are possible:

1. Passively allow the authentication
2. With user intervention, grant access

User intervention must occur before the time specified in request_timeout_ts.
If it does not occur in this time, the device should display a message
indicating that the authentication flow has timed out and should be tried again.
The Endless Computer should also cease to display any user-interaction forms
regarding the authentication.

Once the Endless Computer has decided what to do with the authentication
request, it should store the device’s unique identifier as specified in the
`deviceUUID` querystring parameter along with its permissions in a persistent
store somewhere on the Endless Computer.

If the device will not be authorised, then the Endless Computer should return a
response with the error code (EOS_COMPANION_APP, DEVICE_NOT_AUTHORIZED).

The following payload should be returned:

    200
    Content-Type: application/json
    ---
    {
        "status": [“ok” or “error”],
        "error": [null or {
            "domain": [machine-readable string error domain],
            "code": [machine-readable string error code],
            "detail": [error-specific JSON object adding additional context behind
                       the error]
        }]
    }

If the Endless Computer responds with "status": “ok”, the device may continue to
request content as specified in the next section. If the Endless Computer
responded with “status”: “error” then the “error” field of the response and a
human-readable error message deserialized from “domain” and “code” should be
displayed to the user.

# Error Codes
See [Error Codes](/docs/API.md#error-codes) for more information.

