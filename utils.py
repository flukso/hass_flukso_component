import logging

from homeassistant.const import (TEMP_CELSIUS, VOLUME_LITERS, PRESSURE_HPA, DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_PRESSURE)

_LOGGER = logging.getLogger(__name__)

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
