import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.sensor import PLATFORM_SCHEMA as MQTT_SENSOR_PLATFORM_SCHEMA
from homeassistant.components.mqtt.sensor import MqttSensor
from custom_components.flukso import get_sensor_details
from homeassistant.components.sensor import ENTITY_ID_FORMAT

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("No discovery info for flukso platform sensor")
        return

    _LOGGER.info("Setting up flukso platform sensor")

    async def add_new_device(sensor):
        name, device_class, icon, unit_of_measurement = get_sensor_details(sensor)
        _LOGGER.debug("adding sensor %s with id %s", name, sensor["id"])

        mqttsensorconfig = {}
        mqttsensorconfig["platform"] = "mqtt"
        mqttsensorconfig["name"] = name
        if unit_of_measurement:
            mqttsensorconfig["unit_of_measurement"] = unit_of_measurement
        if icon:
            mqttsensorconfig["icon"] = icon
        if device_class:
            mqttsensorconfig["device_class"] = device_class

        mqttsensorconfig["state_topic"] = "/sensor/" + sensor["id"] + "/" +  sensor["data_type"]
        mqttsensorconfig["value_template"] = """{{ value.split(",")[1]|round(0) }}"""
        if "type" in sensor:
            if sensor["type"] == "electricity":
                mqttsensorconfig["state_topic"] = "/sensor/" + sensor["id"] + "/gauge"
            elif sensor["type"] == "temperature":
                mqttsensorconfig["value_template"] = """{{ value.split(",")[1]|round(1) }}"""
            elif sensor["type"] == "battery":
                mqttsensorconfig["value_template"] = """{{ (((value.split(",")[1]|round(1)) / 3.3) * 100)|round(2) }}"""
            elif sensor["type"] == "error":
                mqttsensorconfig["value_template"] = """
                    {% if (value.split(",")[1]|int) > 0 %}
                        On
                    {% else %}
                        Off
                    {% endif %}"""

        mqttsensorconfig["unique_id"] = ENTITY_ID_FORMAT.format(sensor["id"])
        mqttsensorconfig["qos"] = 0
        mqttsensorconfig["force_update"] = True

        config = MQTT_SENSOR_PLATFORM_SCHEMA(mqttsensorconfig)

        # Add device entity
        async_add_devices([MqttSensor(config, None, None)])

    for sensor in discovery_info:
        hass.async_run_job(add_new_device, sensor)
