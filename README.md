# Carrier Infinity Thermostat Controller

Also compatible with Bryant and likely ICP Brands Ion (including Airquest, Arcoaire, 
Comfortmaker, Day&Night, Heil, Keeprite, Tempstar).

This repository contains an HTTP server that can be used to replace the official
Carrier web service that Carrier Infinity thermostats communicate with.  The
idea is to provide a complete replacement for the HTTP server that Carrier runs,
allowing full remote control of the thermostat using open source applications like
[Home Assistant](https://www.home-assistant.io/).

Currently the weather data is still obtained from Carrier's server. Everything else
is local only. This integration breaks Carrier APP and goes all local (except weather).

# Components

The HTTPServer and HTTPClient have been merged into a single application. Utilizing a 
thread for the server and HomeAssistant Sync for the Client.

# How to Use

## HTTP Server

The HTTP serer is now integrated into HomeAssistant Add-On. It will listen on 
port the configured port (default=5000).  In the thermostatic configuration, 
go to Wifi and Advanced Settings. Turn on the proxy setting, enter the IP address 
of the HomeAssitant and configured port.

Note that it will take a while for the thermostat to connect
and completely refresh itself.  In the meanwhile the wifi status may show the
warning symbol acting as though there are connection problems.  After a hour
or more it will eventually settle down and the warning symbol will disappear.
The thermostat only tries to connect to the server periodically even after
changing the wifi settings, and several different calls to the HTTP server
must succeed (sometimes more than once) before the warning symbol disappears.

## Home Assistant Control

Copy the custom_components/carrier_infinity/ directory under homeassistant/ 
here into the config/custom_components/ directory of your Home Assistant 
installation. Alternatively, download via HACS.

Add configuration such as the following to tell Home Assistant your desired port
and notifcations settings.

      climate:
      - platform: carrier_infinity
        port: 5000
        zone_names:
          - House_Furnace_Carr
        notify:
          energy:           #Matches the value in the server POST...See z_record.json
            entity_id: pushovern  #notify.XYZ
            title: Furnace Energy Report
            message: Appended Report
            data:
              priority: 0
              url: "https://www.home-assistant.io/"
              #sound: pianobar
              #attachment: "http://example.com/image.png"
            delete:         #Deletes these DICT values before converting to YAML and sending.
              - "@version"
              - seer
              - hspf
              - cooling
              - hpheat
              - eheat
              - gas
              - reheat
              - fangas
              - fan
             - looppump
          notifications:    #Matches the value in the server POST...See z_record.json
            entity_id: pushovern  #notify.XYZ
            title: Furnace Notification
            #message: MyApped Message
            data:
              priority: 0
              url: "https://www.home-assistant.io/"
              #sound: pianobar
              #attachment: "http://example.com/image.png"
            delete:         #Deletes this DICT values before converting to YAML and sending.
              - "@version"
            muteable: True
    scan_interval: 300

Restart Home Assistant and the thermostat will appear.  Initially Home Assistant
may not show real data from the actual thermostat.  The thermostat must check in
with the HTTP server before any status information can be determined.  Likewise,
temperature and other settings cannot be adjusted until the thermostat has sent
its current configuration to the HTTP server.

On restart of HomeAssistant the integration hangs and will await the thermostat 
to post before completing the startup.

# Notify

Notify has been imbedded to send alerts on configured messages.

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
https://github.com/MizterB/homeassistant-infinitude from which the HomeAssistant 
Climate.py was based on.
