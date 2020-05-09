# Carrier Infinity Thermostat Controller

This repository contains an HTTP server that can be used to replace the official
Carrier web service that Carrier Infinity thermostats communicate with.  The
idea is to provide a complete replacement for the HTTP server that Carrier runs,
allowing full remote control of the thermostat using open source applications like
[Home Assistant](https://www.home-assistant.io/).

Currently the weather data is still obtained from Carrier's server.

# Components

The HTTP server that communicates with the thermostat is in the infinity_proxy/
directory.  A custom component for Home Assistant that will communicate with the
HTTP server is in homeassistant/.

# How to Use

## HTTP Server

Start the HTTP server in infinity_proxy/http_server.py.  It will listen on port
5000.  In the thermostatic configuration, go to Wifi and Advanced Settings.
Turn on the proxy setting, enter the IP address of the system running
http_server.py and port 5000.

Note that it will take a while for the thermostat to connect to http_server.py
and completely refresh itself.  In the meanwhile the wifi status may show the
warning symbol acting as though there are connection problems.  After a hour
or more it will eventually settle down and the warning symbol will disappear.
The thermostat only tries to connect to the server periodically even after
changing the wifi settings, and several different calls to the HTTP server
must succeed (sometimes more than once) before the warning symbol disappears.

## Home Assistant Control

Copy the carrier_infinity/ directory under homeassistant/ here into the
config/custom_components/ directory of your Home Assistant installation. Add
configuration such as the following to tell Home Assistant where the HTTP server
is running:

    climate:
      - platform: carrier_infinity
        host: infinity.internal.cus
        port: 5000

Restart Home Assistant and the thermostat will appear.  Initially Home Assistant
may not show real data from the actual thermostat.  The thermostat must check in
with the HTTP server before any status information can be determined.  Likewise,
temperature and other settings cannot be adjusted until the thermostat has sent
its current configuration to the HTTP server.

# Design

When looking at the HTTP server you may ask why we parse HTTP requests and build
HTTP responses using our own code rather than make use of a library such as Flask.
This project was first attempted using Flask but the thermostat did not accept
the HTTP responses.  As noted in some parts of the code, often embedded devices
use simplified libraries or custom code due to memory or storage constraints and
therefore they do not handle protocols like HTTP in a completely generic way.
The device is tested against one HTTP server, that being Carriers, and so long
as it works with that server the product is complete.

This project is only possible because the thermostat operates over HTTP instead
of HTTPS (another limitation possibly due to device constraints).  The thermostat
does send an OAuth header and presumably the server uses that to authenticate
thermostats in the field but the thermostats don't have any mechanism to
establish trust of the server.

# Acknowledgements and References

This project was inspired by the Infinitude project at
https://github.com/nebulous/infinitude

That project depends on the Carrier servers as it proxies all requests to Carrier.
One main motivation here is to control the thermostat without any dependence on
Carrier.  The other motivation is to try to make the HTTP server more maintainable
than the Perl code in that project.

The other project that formed a basis for the Home Assistant plugin is
https://github.com/MizterB/homeassistant-infinitude
