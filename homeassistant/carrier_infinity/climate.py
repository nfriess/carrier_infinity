
import logging
import requests
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice,PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_FAN_ONLY,
    FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH,
    CURRENT_HVAC_OFF, CURRENT_HVAC_HEAT, CURRENT_HVAC_COOL, CURRENT_HVAC_IDLE,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_RANGE, SUPPORT_FAN_MODE, SUPPORT_PRESET_MODE,
    DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, ATTR_TEMPERATURE, TEMP_FAHRENHEIT, TEMP_CELSIUS, ATTR_ENTITY_ID)

from homeassistant.helpers import config_validation as cv, entity_platform, service

DOMAIN = "carrier_infinity"


# Activity names
ACTIVITY_SCHEDULE = "schedule"
ACTIVITY_HOME = "home"
ACTIVITY_AWAY = "away"
ACTIVITY_SLEEP = "sleep"
ACTIVITY_WAKE = "wake"
ACTIVITY_MANUAL = "manual"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=5000): cv.port,
    vol.Optional("zone", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=9))
})


_LOGGER = logging.getLogger(__name__)


class CarrierInfinity(ClimateDevice):

    def __init__(self, host, port, zone):
        _LOGGER.debug("Create Carrier Infinity using HTTP server %s:%i, zone %i", host, port, zone)
        self._host = host
        self._port = port
        self._zone = 1

        self._temperature_unit = TEMP_CELSIUS
        # HVAC_MODE_COOL, HVAC_MODE_AUTO, HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY
        self._hvac_mode = HVAC_MODE_HEAT
        # CURRENT_HVAC_OFF, CURRENT_HVAC_HEAT, CURRENT_HVAC_COOL
        self._hvac_action = CURRENT_HVAC_IDLE
        self._preset_mode = ACTIVITY_MANUAL
        self._temperature = 20.0
        self._humidity = 30
        self._target_temperature = 20.0
        # FAN_ON, FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH,
        self._fan = FAN_AUTO

        self.update()


    def update(self):

        url = "http://{}:{}/api/config/{}".format(self._host, self._port, self._zone)
        try:
            resp = requests.get(url, timeout=1)
        except requests.exceptions.Timeout:
            _LOGGER.error("HTTP server timed out")
            return

        if resp.status_code != requests.codes.ok:
            _LOGGER.error("HTTP server returned %i", resp.status_code)
            return

        jsonObj = resp.json()

        if jsonObj['mode'] == "heat":
            self._hvac_mode = HVAC_MODE_HEAT
        elif jsonObj['mode'] == "cool":
            self._hvac_mode = HVAC_MODE_COOL
        else:
            _LOGGER.error("Unknown mode: %s", jsonObj['mode'])
            self._hvac_mode = HVAC_MODE_HEAT


        if jsonObj['units'] == "C":
            self._temperature_unit = TEMP_CELSIUS
        elif jsonObj['units'] == "F":
            self._temperature_unit = TEMP_FAHRENHEIT
        else:
            _LOGGER.error("Unknown units: %s", jsonObj['units'])
            self._temperature_unit = TEMP_CELSIUS

        url = "http://{}:{}/api/status/{}".format(self._host, self._port, self._zone)
        try:
            resp = requests.get(url, timeout=1)
        except requests.exceptions.Timeout:
            _LOGGER.error("HTTP server timed out")
            return

        if resp.status_code != requests.codes.ok:
            _LOGGER.error("HTTP server returned %i", resp.status_code)
            return

        jsonObj = resp.json()

        if jsonObj['zoneConditioning'] == "idle":
            self._hvac_action = CURRENT_HVAC_IDLE
        elif jsonObj['zoneConditioning'] == "active_heat":
            self._hvac_action = CURRENT_HVAC_HEAT
        elif jsonObj['zoneConditioning'] == "active_cool":
            self._hvac_action = CURRENT_HVAC_COOL
        else:
            _LOGGER.error("Unknown zoneConditioning: %s", jsonObj['zoneConditioning'])
            self._hvac_action = CURRENT_HVAC_IDLE

        self._temperature = float(jsonObj['temperature'])
        self._humidity = float(jsonObj['humidity'])

        if self._hvac_mode == HVAC_MODE_HEAT:
            self._target_temperature = float(jsonObj['heatTo'])
        else:
            self._target_temperature = float(jsonObj['coolTo'])

        self._preset_mode = jsonObj['activity']

        if jsonObj['fan'] == "off":
            self._fan = FAN_AUTO
        else:
            _LOGGER.error("Unknown fan: %s", jsonObj['fan'])
            self._hvac_mode = HVAC_MODE_HEAT

        # hold
        # until



    # Generic properties

    @property
    def available(self):
        # Can set to false if http server is not working
        return True

    @property
    def name(self):
        return "Carrier Infinity Thermostat"

    @property
    def should_poll(self):
        return True

    @property
    def unique_id(self):
        # TOOD: Serial number
        return "W00000"

    # Climate specific properties

    @property
    def temperature_unit(self):
        return self._temperature_unit

    @property
    def precision(self):
        return 0.1

    @property
    def current_temperature(self):
        return self._temperature

    @property
    def current_humidity(self):
        return self._humidity

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def target_temperature_high(self):
        return self._target_temperature

    @property
    def target_temperature_low(self):
        return self._target_temperature

    @property
    def target_temperature_step(self):
        return 0.5

    @property
    def max_temp(self):
        return 25

    @property
    def min_temp(self):
        return 16

    # Don't support min_humidity, max_humidity

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def hvac_action(self):
        return self._hvac_action

    @property
    def hvac_modes(self):
        # HVAC_MODE_COOL, HVAC_MODE_AUTO, HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY
        return [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY]

    @property
    def preset_mode(self):
        return self._preset_mode

    @property
    def preset_modes(self):
        return [ACTIVITY_WAKE, ACTIVITY_AWAY, ACTIVITY_HOME, ACTIVITY_SLEEP, ACTIVITY_MANUAL]

    @property
    def fan_mode(self):
        return self._fan

    @property
    def fan_modes(self):
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    # Don't support swing_mode, swing_modes, is_aux_heat

    @property
    def supported_features(self):
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE


    # Methods
    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.info("Carrier Infinity set hvac")

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        self.set_hold(preset_mode, None)

    def set_fan_mode(self, fan_mode):
        _LOGGER.info("Carrier Infinity set fan")
        """Set new target fan mode."""

    def set_temperature(self, **kwargs):
        """Set new target temperature."""

        temperature = kwargs.get(ATTR_TEMPERATURE)
        self.set_hold("manual", temperature)


    # Services
    def set_hold(self, activity, temperature=None, until=None):

        url = "http://{}:{}/api/hold/{}".format(self._host, self._port, self._zone)

        data = {
            "hold": "on",
            "activity": activity
        }

        if temperature:
            data["temp"] = str(temperature)
        if until:
            data["until"] = until

        try:
            resp = requests.post(url, data, timeout=1)
        except requests.exceptions.Timeout:
            _LOGGER.error("HTTP server timed out")
            return

        if resp.status_code != requests.codes.ok:
            _LOGGER.error("HTTP server returned %i", resp.status_code)
            return


    def clear_hold(self):

        url = "http://{}:{}/api/hold/{}".format(self._host, self._port, self._zone)

        data = {
            "hold": "off"
        }

        try:
            resp = requests.post(url, data, timeout=1)
        except requests.exceptions.Timeout:
            _LOGGER.error("HTTP server timed out")
            return

        if resp.status_code != requests.codes.ok:
            _LOGGER.error("HTTP server returned %i", resp.status_code)
            return




def setup_platform(hass, config, add_entities, discovery_info=None):

    _LOGGER.info("Setup Carrier Infinity")

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    zone = config.get("zone")

    infinity = CarrierInfinity(host, port, zone)

    add_entities([infinity])

    _LOGGER.info("Setup Carrier Infinity Services")

    def handle_set_hold(call):
        activity = call.data.get("activity")
        temperature = call.data.get("temperature")
        until = call.data.get("until")
        infinity.set_hold(activity, temperature, until)

    def handle_clear_hold(call):
        infinity.clear_hold()

    hass.services.register(DOMAIN, "set_hold", handle_set_hold)
    hass.services.register(DOMAIN, "clear_hold", handle_clear_hold)
