import logging
import json
import voluptuous as vol
from datetime import timedelta

from homeassistant.components import mqtt
from homeassistant.const import (TEMP_CELSIUS, VOLUME_LITERS, PRESSURE_HPA, DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_PRESSURE)
from homeassistant.core import callback
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

DEPENDENCIES = ["mqtt"]

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_SENSORS = "ignore_sensors"

DOMAIN = "flukso"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_IGNORE_SENSORS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)  # what does this mean?

sensor_config = {}
kube_config = {}
flx_config = {}


def get_sensor_details(sensor):
    name = "flukso sensor"
    if "name" in sensor:
        name = sensor["name"]
    device_class = None
    icon = None
    unit_of_measurement = None

    if "type" in sensor:
        name = name + " " + sensor["type"]
        if sensor["type"] == "electricity":
            if "subtype" in sensor:
                name = name + " " + sensor["subtype"]
                if sensor["subtype"] == "q1":
                    unit_of_measurement = "VAR"
                elif sensor["subtype"] == "q2":
                    unit_of_measurement = "VAR"
                elif sensor["subtype"] == "q3":
                    unit_of_measurement = "VAR"
                elif sensor["subtype"] == "q4":
                    unit_of_measurement = "VAR"
                elif sensor["subtype"] == "pplus":
                    unit_of_measurement = "W"
                elif sensor["subtype"] == "pminus":
                    unit_of_measurement = "W"
                elif sensor["subtype"] == "vrms":
                    unit_of_measurement = "V"
                elif sensor["subtype"] == "irms":
                    unit_of_measurement = "A"
                elif sensor["subtype"] == "pf":
                    unit_of_measurement = ""
                elif sensor["subtype"] == "vthd":
                    unit_of_measurement = ""
                elif sensor["subtype"] == "ithd":
                    unit_of_measurement = ""
                else:
                    unit_of_measurement = ""
                    _LOGGER.warning("Unknown subtype: %s", sensor["subtype"])
            icon = "mdi:flash"
        elif sensor["type"] == "temperature":
            device_class = DEVICE_CLASS_TEMPERATURE
            unit_of_measurement = TEMP_CELSIUS
        elif sensor["type"] == "movement":
            device_class = "motion"
        elif sensor["type"] == "pressure":
            device_class = DEVICE_CLASS_PRESSURE
            unit_of_measurement = PRESSURE_HPA
        elif sensor["type"] == "battery":
            device_class = DEVICE_CLASS_BATTERY
            unit_of_measurement = "%"
        elif sensor["type"] == "vibration":
            device_class = "vibration"
        elif sensor["type"] == "error":
            device_class = "problem"
        elif sensor["type"] == "water":
            icon = "mdi:water"
            unit_of_measurement = VOLUME_LITERS
        elif sensor["type"] == "light":
            device_class = DEVICE_CLASS_ILLUMINANCE
            unit_of_measurement = "lx"
        elif sensor["type"] == "proximity":
            icon = "mdi:ruler"
        elif sensor["type"] == "humidity":
            device_class = DEVICE_CLASS_HUMIDITY
            unit_of_measurement = "%"
        elif sensor["type"] == "gas":
            icon = "mdi:gas-station"
            unit_of_measurement = VOLUME_LITERS
        else:
            _LOGGER.warning("Unknown type: %s", sensor["type"])

    return name, device_class, icon, unit_of_measurement

async def async_setup(hass, config):

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
