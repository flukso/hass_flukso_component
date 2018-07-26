"""
Component to make instant statistics about your history.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.history_stats/
"""
import datetime
import logging
import math

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_TOKEN,
    EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tmpo'
REQUIREMENTS = ['tmpo==0.2.10']

CONF_SENSOR = 'sensor'
CONF_START = 'start'
CONF_END = 'end'
CONF_DURATION = 'duration'
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

DEFAULT_NAME = 'unnamed sensor'
ICON = 'mdi:chart-line'

ATTR_VALUE = 'value'

def exactly_two_period_keys(conf):
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    if sum(param in conf for param in CONF_PERIOD_KEYS) != 2:
        raise vol.Invalid('You must provide exactly 2 of the following:'
                          ' start, end, duration')
    return conf


PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSOR): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_START): cv.template,
    vol.Optional(CONF_END): cv.template,
    vol.Optional(CONF_DURATION): cv.time_period,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}), exactly_two_period_keys)


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the History Stats sensor."""
    sensor = config.get(CONF_SENSOR)
    token = config.get(CONF_TOKEN)
    start = config.get(CONF_START)
    end = config.get(CONF_END)
    duration = config.get(CONF_DURATION)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    name = config.get(CONF_NAME)

    for template in [start, end]:
        if template is not None:
            template.hass = hass

    add_devices([FluksoTmpoSensor(hass, sensor, token, start, end,
                                    duration, unit_of_measurement, name)])

    return True


class FluksoTmpoSensor(Entity):
    """Representation of a HistoryStats sensor."""

    def __init__(
            self, hass, sensor, token, start, end, duration,
            unit_of_measurement, name):
        """Initialize the HistoryStats sensor."""
        import tmpo
        self._hass = hass

        self._sensor = sensor
        self._token = token
        self._duration = duration
        self._start = start
        self._end = end
        self._name = name
        self._unit_of_measurement = unit_of_measurement

        self._period = (datetime.datetime.now(), datetime.datetime.now())
        self.value = None
        
        cache_dir = self._hass.config.path("tmpo")
        if not os.path.isdir(cache_dir):
            _LOGGER.info("Create cache dir %s.", cache_dir)
            os.mkdir(cache_dir)
        
        self._session = tmpo.Session(path=cache_dir)
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
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        # Get previous values of start and end
        p_start, p_end = self._period

        # Parse templates
        self.update_period()
        start, end = self._period
        
        _LOGGER.debug("Period %s %s", start, end)

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

        _LOGGER.debug("Period (int) %s %s", start_timestamp, end_timestamp)

        # If period has not changed and current time after the period end...
        if start_timestamp == p_start_timestamp and \
            end_timestamp == p_end_timestamp and \
                end_timestamp <= now_timestamp:
            # Don't compute anything as the value cannot have changed
            _LOGGER.debug("Period has not changed, do nothing.")
            return

        _LOGGER.debug("Period has changed, syncing...")

        self._session.sync()
        
        sensor_series = self._session.series(self._sensor, head=start_timestamp, tail=end_timestamp)
        
        self.value = sensor_series.diff().sum()

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


class FluksoTmpoHelper:
    """Static methods to make the HistoryStatsSensor code lighter."""

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
