"""The Flukso integration."""
import logging
import json
import voluptuous as vol
from datetime import timedelta

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import (DOMAIN, CONF_IGNORE_SENSORS)
from .utils import get_sensor_details

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_IGNORE_SENSORS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)  # what does this mean?

sensor_config = {}
kube_config = {}
flx_config = {}

async def async_setup(hass, config):
    """Set up the Flukso component."""

    conf = config[DOMAIN]
    ignored_sensors = conf.get(CONF_IGNORE_SENSORS)

    _LOGGER.debug(ignored_sensors)

    store = hass.data.get(DOMAIN)
    if store is None:
        store = hass.data[DOMAIN] = {}

    unsubscribe = None

    @callback
    def config_message_received(msg):
        splitted_topic = msg.topic.split("/")

        device = splitted_topic[2]
        conftype = splitted_topic[4]

        _LOGGER.debug("storing type %s for device %s", conftype, device)
        if device not in store:
            store[device] = {}
        store[device][conftype] = json.loads(msg.payload)

    async def unsubscribe_config_topics(time):
        if unsubscribe:
            _LOGGER.debug("unsubscribing from config topics")
            unsubscribe()
        else:
            _LOGGER.error("unsubscribing from config topics failed")

        sensors = []
        binary_sensors = []

        for deviceid, deviceconfig in store.items():
            _LOGGER.debug("getting sensors of device id %s", deviceid)
            if "flx" not in deviceconfig:
                _LOGGER.error("no flx entry in config of device with id: %s", deviceid)
                hass.data[DOMAIN] = {}
                return
            if "kube" not in deviceconfig:
                _LOGGER.error("no kube entry in config of device with id: %s", deviceid)
                hass.data[DOMAIN] = {}
                return
            if "sensor" not in deviceconfig:
                _LOGGER.error("no sensor entry in config of device with id: %s", deviceid)
                hass.data[DOMAIN] = {}
                return

            flx_config = deviceconfig["flx"]
            kube_config = deviceconfig["kube"]
            sensor_config = deviceconfig["sensor"]

            for key, sensor in sensor_config.items():
                if "enable" not in sensor or sensor["enable"] == 0:
                    continue
                if "tmpo" in sensor and sensor["tmpo"] == 0:
                    continue
                if sensor["id"] in ignored_sensors:
                    continue
                if "class" in sensor and sensor["class"] == "kube":
                    if ("name" in kube_config[str(sensor["kid"])] and
                            kube_config[str(sensor["kid"])]["name"]):
                        sensor["name"] = kube_config[str(sensor["kid"])]["name"]
                    else:
                        sensor["name"] = "unknown"
                    if ("type" in sensor and (sensor["type"] == "movement" or
                            sensor["type"] == "vibration" or sensor["type"] == "error")):
                        binary_sensors.append(sensor)
                    elif "type" in sensor and sensor["type"] == "proximity":
                        _LOGGER.debug("Ignoring proximity sensor: %s",
                            sensor["name"])
                    else:
                        sensors.append(sensor)
                else:
                    if "port" in sensor:
                        if ("name" in flx_config[str(sensor["port"][0])] and
                                flx_config[str(sensor["port"][0])]["name"]):
                            sensor["name"] = flx_config[str(sensor["port"][0])
                                    ]["name"]
                        else:
                            sensor["name"] = "unknown"
                    sensors.append(sensor)

        _LOGGER.debug("Loading platforms")
        load_platform(hass, "sensor", DOMAIN, sensors, config)
        load_platform(hass, "binary_sensor", DOMAIN, binary_sensors, config)
        _LOGGER.debug("Done loading platforms")

    unsubscribe = await mqtt.async_subscribe(hass, '/device/+/config/+', config_message_received)

    # we assume that all config messages are received after 5 seconds
    async_track_point_in_time(hass, unsubscribe_config_topics, dt_util.utcnow() + timedelta(seconds=5))

    return True
