import asyncio
import logging
from typing import Optional

import homeassistant.components.mqtt as mqtt
from homeassistant.helpers.entity import Entity
from custom_components.flukso import (FLUKSO_CLIENT, cv, vol, get_sensor_details)
from homeassistant.core import callback
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import template
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.util import slugify

DEPENDENCIES = ['flukso']

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error('No discovery info for flukso platform sensor')
        return

    _LOGGER.info('Setting up flukso platform sensor')

    @asyncio.coroutine
    def add_new_device(sensor):
        default_template = template.Template('{{ value.split(",")[1]|float }}', hass)

        name, device_class, icon, unit_of_measurement = get_sensor_details(sensor)

        _LOGGER.debug('adding sensor %s with id %s', name, sensor['id'])
        data_type = sensor['data_type']
        if 'type' in sensor:
            if sensor['type'] == 'electricity':
                data_type = 'gauge'

        fluksosensor = FluksoSensor(name=name, state_topic="/sensor/"+sensor['id']+"/"+data_type, qos=0, unit_of_measurement=unit_of_measurement, force_update=True, expire_after=None, icon=icon, device_class=device_class, value_template=default_template, json_attributes=[], unique_id=ENTITY_ID_FORMAT.format('{}_{}'.format(slugify(name), sensor['id'])))
        # Add device entity
        async_add_devices([fluksosensor])

    for sensor in discovery_info:
        hass.async_run_job(add_new_device, sensor)

class FluksoSensor(Entity):

    def __init__(self, name, state_topic, qos, unit_of_measurement,
                 force_update, expire_after, icon, device_class: Optional[str],
                 value_template, json_attributes, unique_id: Optional[str]):

        self._state = STATE_UNKNOWN
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement
        self._force_update = force_update
        self._template = value_template
        self._expire_after = expire_after
        self._icon = icon
        self._device_class = device_class
        self._expiration_trigger = None
        self._json_attributes = set(json_attributes)
        self._unique_id = unique_id
        self._attributes = None
        self.entity_id = unique_id

    async def async_added_to_hass(self):

        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            # auto-expire enabled?
            if self._expire_after is not None and self._expire_after > 0:
                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()
                    self._expiration_trigger = None

                # Set new trigger
                expiration_at = (
                    dt_util.utcnow() + timedelta(seconds=self._expire_after))

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self.value_is_expired, expiration_at)

            if self._json_attributes:
                self._attributes = {}
                try:
                    json_dict = json.loads(payload)
                    if isinstance(json_dict, dict):
                        attrs = {k: json_dict[k] for k in
                                 self._json_attributes & json_dict.keys()}
                        self._attributes = attrs
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("MQTT payload could not be parsed as JSON")
                    _LOGGER.warning("Erroneous JSON: %s", payload)

            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload, self._state)
            self._state = payload
            self.async_schedule_update_ha_state()

        await self.hass.data[FLUKSO_CLIENT].async_subscribe(self._state_topic, message_received, self._qos, 'utf-8')

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._state = STATE_UNKNOWN
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class