import asyncio
import logging
from datetime import timedelta
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorDevice
from custom_components.flukso import (FLUKSO_CLIENT, cv, vol, get_sensor_details)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.core import callback
from homeassistant.util.dt import utcnow
from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT
from homeassistant.util import slugify

DEFAULT_TIMEOUT = 10

DEPENDENCIES = ['flukso']

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error('No discovery info for flukso platform binary sensor')
        return

    _LOGGER.info('Setting up flukso platform binary sensor')

    @asyncio.coroutine
    def add_new_device(sensor):
        name, device_class, _, _ = get_sensor_details(sensor)
        _LOGGER.debug('adding binary sensor %s with id %s', name, sensor['id'])
        
        kubemotionsensor = KubeMotionDevice(hass=hass, name=name, state_topic="/sensor/"+sensor['id']+"/"+sensor['data_type'], device_class=device_class, qos=0, force_update=False, timeout=DEFAULT_TIMEOUT, unique_id=ENTITY_ID_FORMAT.format('{}_{}'.format(slugify(name), sensor['id'])))
        # Add device entity
        async_add_devices([kubemotionsensor])

    for sensor in discovery_info:
        hass.async_run_job(add_new_device, sensor)

class KubeMotionDevice(BinarySensorDevice):

    def __init__(self, hass, name, state_topic, device_class,
                 qos, force_update, timeout,
                 unique_id: Optional[str]):

        self._hass = hass
        self._name = name
        self._state = None
        self._state_topic = state_topic
        self._device_class = device_class
        self._timeout = timeout
        self._qos = qos
        self._force_update = force_update
        self._unique_id = unique_id
        self._timer = None
        self.entity_id = unique_id

    @asyncio.coroutine
    def async_added_to_hass(self):

        @callback
        def state_message_received(topic, payload, qos):
            """Handle a new received MQTT state message."""
            # we do not care about the payload
            if self._state:
                # stop the currect running timer
                if self._timer is not None:
                    self._timer()
                    self._timer = None
            else:
                self._state = True

            # start the timer
            _LOGGER.debug('starting motion timeout for entity: %s with state_topic: %s', self._name, self._state_topic)
            
            if self._timeout > 0:
                def _delay_turn_off(now):
                    _LOGGER.debug("%s called delayed (%s sec) turn off", self._name, self._timeout)
                    self._state = False
                    self.async_schedule_update_ha_state()
                    self._timer = None

                self._timer = async_track_point_in_utc_time(self._hass, _delay_turn_off, utcnow() + timedelta(seconds=self._timeout))
                self.async_schedule_update_ha_state()
            else:
                _LOGGER.error('Timeout for entity: %s has a bad value: %d', self._name, self._timeout)

        mqttc = self._hass.data[FLUKSO_CLIENT]
        mqttc.message_callback_add(self._state_topic, state_message_received)
        mqttc.loop_start()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id