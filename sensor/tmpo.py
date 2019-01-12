"""
Component to get tmpo data from flukso

For more information about tmpo, visit
https://github.com/flukso/tmpo-py
"""
import datetime
import logging
import math
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_TOKEN, CONF_SCAN_INTERVAL,
    CONF_SENSORS, CONF_FRIENDLY_NAME, CONF_ICON, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tmpo'
REQUIREMENTS = ['tmpo==0.2.10']

CONF_SENSOR = 'sensor'
CONF_START = 'start'
CONF_END = 'end'
CONF_DURATION = 'duration'
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

DEFAULT_ICON = 'mdi:flash'
DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=5)

ATTR_VALUE = 'value'

def exactly_two_period_keys(conf):
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    if sum(param in conf for param in CONF_PERIOD_KEYS) != 2:
        raise vol.Invalid('You must provide exactly 2 of the following:'
                          ' start, end, duration')
    return conf


SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_SENSOR): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_START): cv.template,
    vol.Optional(CONF_END): cv.template,
    vol.Optional(CONF_DURATION): cv.time_period,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period,
}, exactly_two_period_keys)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})

# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the tmpo sensors."""

    _LOGGER.info("Starting up tmpo platform")
    sensors = []
    session = FluksoTmpoSession(hass)

    for device, device_config in config[CONF_SENSORS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        sensor = device_config.get(CONF_SENSOR)
        token = device_config.get(CONF_TOKEN)
        start = device_config.get(CONF_START)
        end = device_config.get(CONF_END)
        duration = device_config.get(CONF_DURATION)
        unit_of_measurement = device_config.get(CONF_UNIT_OF_MEASUREMENT)
        scan_interval = device_config.get(CONF_SCAN_INTERVAL)
        icon = device_config.get(CONF_ICON)
        _LOGGER.debug("icon for %s: %s", friendly_name, str(icon))

        for template in [start, end]:
            if template is not None:
                template.hass = hass

        sensors.append(FluksoTmpoSensor(hass, session, sensor, token, start,
            end, duration, unit_of_measurement, device, icon, friendly_name,
            scan_interval))

    if not sensors:
        _LOGGER.error("No tmpo sensors added")
        return False

    _LOGGER.info("Adding sensors")
    add_devices(sensors)
    return True

class FluksoTmpoSensor(Entity):
    """Representation of a tmpo flukso sensor."""

    def __init__(
            self, hass, session, sensor, token, start, end, duration,
            unit_of_measurement, device, icon, friendly_name, scan_interval):
        """Initialize the Flukso Tmpo sensor."""
        self._hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device,
                hass=hass)
        self._session = session
        self._sensor = sensor
        self._token = token
        self._duration = duration
        self._start = start
        self._end = end
        self._icon = icon
        self._name = friendly_name
        self._unit_of_measurement = unit_of_measurement
        self._scan_interval = scan_interval
        self._period = (datetime.datetime.now(), datetime.datetime.now())
        self.value = None
        self._last_updated = None

        # Add sensor to the flukso tmpo session
        self._session.add(self._sensor, self._token)

        def force_refresh(*args):
            """Force the component to refresh."""
            self.schedule_update_ha_state(True)

        # Update value when home assistant starts
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, force_refresh)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.value is None:
            return {}

        return {
            ATTR_VALUE: self.value,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data and updates the states."""
        # Get previous values of start and end
        p_start, p_end = self._period

        # Parse templates
        self.update_period()
        start, end = self._period

        # Convert times to UTC
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end)
        p_start = dt_util.as_utc(p_start)
        p_end = dt_util.as_utc(p_end)
        now = datetime.datetime.now()

        # Compute integer timestamps
        start_timestamp = math.floor(dt_util.as_timestamp(start))
        end_timestamp = math.floor(dt_util.as_timestamp(end))
        p_start_timestamp = math.floor(dt_util.as_timestamp(p_start))
        p_end_timestamp = math.floor(dt_util.as_timestamp(p_end))
        now_timestamp = math.floor(dt_util.as_timestamp(now))

        # If period has not changed and current time after the period end...
        if start_timestamp == p_start_timestamp and \
            end_timestamp == p_end_timestamp and \
                end_timestamp <= now_timestamp:
            # Don't compute anything as the value cannot have changed
            _LOGGER.debug("Values for %s have not changed", self._name)
            return

        if self._last_updated and (self._last_updated +
                self._scan_interval.total_seconds()) > now_timestamp:
            # no need to update yet
            _LOGGER.debug("No need to update %s yet", self._name)
            return

        self._session.sync(self._scan_interval)

        _LOGGER.debug("Synced %s, updating value", self._name)

        sensor_series = self._session.tmposession.series(self._sensor,
                head=start_timestamp, tail=end_timestamp)

        self.value = sensor_series.diff().sum()
        _LOGGER.debug("Value for %s updated", self._name)
        self._last_updated = now_timestamp

    def update_period(self):
        """Parse the templates and store a datetime tuple in _period."""
        start = None
        end = None

        # Parse start
        if self._start is not None:
            try:
                start_rendered = self._start.render()
            except (TemplateError, TypeError) as ex:
                FluksoTmpoHelper.handle_template_exception(ex, 'start')
                return
            start = dt_util.parse_datetime(start_rendered)
            if start is None:
                try:
                    start = dt_util.as_local(dt_util.utc_from_timestamp(
                        math.floor(float(start_rendered))))
                except ValueError:
                    _LOGGER.error("Parsing error: start must be a datetime"
                                  "or a timestamp")
                    return

        # Parse end
        if self._end is not None:
            try:
                end_rendered = self._end.render()
            except (TemplateError, TypeError) as ex:
                FluksoTmpoHelper.handle_template_exception(ex, 'end')
                return
            end = dt_util.parse_datetime(end_rendered)
            if end is None:
                try:
                    end = dt_util.as_local(dt_util.utc_from_timestamp(
                        math.floor(float(end_rendered))))
                except ValueError:
                    _LOGGER.error("Parsing error: end must be a datetime "
                                  "or a timestamp")
                    return

        # Calculate start or end using the duration
        if start is None:
            start = end - self._duration
        if end is None:
            end = start + self._duration

        self._period = start, end

class FluksoTmpoSession:
    def __init__(self, hass):
        import tmpo

        cache_dir = hass.config.path("tmpo")
        if not os.path.isdir(cache_dir):
            _LOGGER.info("Create cache dir %s", cache_dir)
            os.mkdir(cache_dir)

        self._session = tmpo.Session(path=cache_dir)
        self._last_sync = None

    def add(self, sensor, token):
        now = datetime.datetime.now()
        self._session.add(sensor, token)
        self._session.sync()
        self._last_sync = now
        _LOGGER.debug("Sync done")

    def sync(self, interval):
        now = datetime.datetime.now()

        if not self._last_sync:
            self._session.sync()
            self._last_sync = now
            _LOGGER.debug("Sync done")
            return True
        else:
            # Compute integer timestamps
            last_sync_timestamp = math.floor(dt_util.as_timestamp(
                self._last_sync))
            now_timestamp = math.floor(dt_util.as_timestamp(now))

            # wait for interval seconds to update the value
            if (last_sync_timestamp + interval.total_seconds()) <=
                    now_timestamp:
                self._session.sync()
                self._last_sync = now
                _LOGGER.debug("Sync done")
                return True
            else:
                return False

    @property
    def tmposession(self):
        return self._session

class FluksoTmpoHelper:
    """Static methods to make the FluksoTmpoSensor code lighter."""

    @staticmethod
    def handle_template_exception(ex, field):
        """Log an error nicely if the template cannot be interpreted."""
        if ex.args and ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning(ex)
            return
        _LOGGER.error("Error parsing template for field %s", field)
        _LOGGER.error(ex)

