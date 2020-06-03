import asyncio
import logging

from homeassistant.components.mqtt.binary_sensor import PLATFORM_SCHEMA as MQTT_BINARY_SENSOR_PLATFORM_SCHEMA
from homeassistant.components.mqtt.binary_sensor import MqttBinarySensor
from custom_components.flukso import get_sensor_details
from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_devices,
    discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("No discovery info for flukso platform binary sensor")
        return

    _LOGGER.info("Setting up flukso platform binary sensor")

    async def add_new_device(sensor):
        name, device_class, _, _ = get_sensor_details(sensor)
        _LOGGER.debug("adding binary sensor %s with id %s", name, sensor["id"])

        mqttsensorconfig = {}

        mqttsensorconfig["platform"] = "mqtt"
        mqttsensorconfig["name"] = name
        mqttsensorconfig["state_topic"] = "/sensor/" + sensor["id"] + "/" + sensor["data_type"]
        if device_class:
            mqttsensorconfig["device_class"] = device_class

        if device_class and (device_class == "problem"):
            mqttsensorconfig["value_template"] = """
                {% if (value.split(",")[1]|int) > 0 %}
                    ON
                {% else %}
                    OFF
                {% endif %}"""
        else:
            mqttsensorconfig["off_delay"] = DEFAULT_TIMEOUT
            mqttsensorconfig["value_template"] = """
                {% if value %}
                    ON
                {% else %}
                    OFF
                {% endif %}"""

        mqttsensorconfig["unique_id"] = ENTITY_ID_FORMAT.format(sensor["id"])
        mqttsensorconfig["qos"] = "0"
        mqttsensorconfig["force_update"] = "false"

        config = MQTT_BINARY_SENSOR_PLATFORM_SCHEMA(mqttsensorconfig)

        # Add device entity
        async_add_devices([MqttBinarySensor(config, None, None)])

    for sensor in discovery_info:
        hass.async_run_job(add_new_device, sensor)
