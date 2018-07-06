import asyncio
import logging
import json
import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT, TEMP_CELSIUS, VOLUME_LITERS, DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE,
DEVICE_CLASS_TEMPERATURE)
from homeassistant.core import callback
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
async_dispatcher_connect)

REQUIREMENTS = ['paho-mqtt==1.3.1']

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_DEVICES = 'ignore_devices'

BINARY_SENSOR_ADD_CALLBACK = 'flukso_add_binary_sensor'
SENSOR_ADD_CALLBACK = 'flukso_add_sensor'

DOMAIN = 'flukso'
FLUKSO_CLIENT = 'flukso_client'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=1883): cv.port,
        vol.Optional(CONF_IGNORE_DEVICES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA) # what does this mean?

sensor_config = {}
kube_config = {}
flx_config = {}

def get_sensor_details(sensor):
    name = 'flukso sensor'
    if 'name' in sensor:
        name = sensor['name']
    device_class = 'None'
    icon = ''
    unit_of_measurement = ''

    if 'type' in sensor:
        if sensor['type'] == 'electricity':
            if 'subtype' in sensor:
                name = name + ' ' + sensor['subtype']
                if sensor['subtype'] == 'q1':
                    unit_of_measurement = 'VAR'
                elif sensor['subtype'] == 'q2':
                    unit_of_measurement = 'VAR'
                elif sensor['subtype'] == 'q3':
                    unit_of_measurement = 'VAR'
                elif sensor['subtype'] == 'q4':
                    unit_of_measurement = 'VAR'
                elif sensor['subtype'] == 'pplus':
                    unit_of_measurement = 'W'
                elif sensor['subtype'] == 'pminus':
                    unit_of_measurement = 'W'
                elif sensor['subtype'] == 'vrms':
                    unit_of_measurement = 'V'
                elif sensor['subtype'] == 'irms':
                    unit_of_measurement = 'A'
                # elif sensor['subtype'] == 'pf':
                #     unit_of_measurement = ''
                # elif sensor['subtype'] == 'vthd':
                #     unit_of_measurement = ''
                # elif sensor['subtype'] == 'ithd':
                #     unit_of_measurement = ''
                # elif sensor['subtype'] == 'alpha':
                #     unit_of_measurement = ''
                else:
                    unit_of_measurement = ''
                    _LOGGER.warning('Unknown subtype: %s', sensor['subtype'])
            icon = 'mdi:flash'
            device_class = 'None'
        elif sensor['type'] == 'temperature':
            name = name + ' ' + sensor['type']
            device_class = DEVICE_CLASS_TEMPERATURE
            icon = 'mdi:thermometer'
            unit_of_measurement = TEMP_CELSIUS
        elif sensor['type'] == 'movement':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:run-fast'
            unit_of_measurement = ''
        elif sensor['type'] == 'pressure':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:weight'
            unit_of_measurement = 'Pa'
        elif sensor['type'] == 'battery':
            name = name + ' ' + sensor['type']
            device_class = DEVICE_CLASS_BATTERY
            icon = 'mdi:battery'
            unit_of_measurement = 'V'
        elif sensor['type'] == 'vibration':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:vibrate'
            unit_of_measurement = ''
        elif sensor['type'] == 'error':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:skull'
            unit_of_measurement = ''
        elif sensor['type'] == 'water':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:water'
            unit_of_measurement = VOLUME_LITERS
        elif sensor['type'] == 'light':
            name = name + ' ' + sensor['type']
            device_class = DEVICE_CLASS_ILLUMINANCE
            icon = 'mdi:white-balance-sunny'
            unit_of_measurement = 'lx'
        elif sensor['type'] == 'proximity':
            name = name + ' ' + sensor['type']
            device_class = 'None'
            icon = 'mdi:ruler'
            unit_of_measurement = ''
        elif sensor['type'] == 'humidity':
            name = name + ' ' + sensor['type']
            device_class = DEVICE_CLASS_HUMIDITY
            icon = 'mdi:water-percent'
            unit_of_measurement = '%'
        elif sensor['type'] == 'gas':
            device_class = 'None'
            icon = 'mdi:gas-station'
            unit_of_measurement = VOLUME_LITERS
        else:
            _LOGGER.warning('Unknown type: %s', sensor['type'])

    return name, device_class, icon, unit_of_measurement

@asyncio.coroutine
def async_setup(hass, config):
    import paho.mqtt.client as mqtt
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    ignored_devices = conf.get(CONF_IGNORE_DEVICES)

    client_id = 'HomeAssistant-FluksoComponent'
    keepalive = 600
    qos = 0

    _LOGGER.debug('Config host: %s port %d', host, port)
    _LOGGER.debug(ignored_devices)

    mqttc = mqtt.Client(client_id)
    # mqttc.username_pw_set(username, password=password)

    @callback
    def on_connect(client, userdata, flags, rc):
        if rc > 0:
            _LOGGER.error("Connected with result code "+str(rc))
        else:
            client.subscribe("/device/+/config/flx")

    @callback
    def on_message(client, userdata, msg):
        global flx_config
        global kube_config
        global sensor_config

        conftype = msg.topic.split("/")[4]

        _LOGGER.debug('configuration type: %s', conftype)

        if conftype == "sensor":
            sensors = []
            binary_sensors = []

            sensor_config = json.loads(msg.payload)
            for key, sensor in sensor_config.items():
                if ('enable' in sensor and sensor['enable'] == 1) and ('tmpo' not in sensor or sensor['tmpo'] == 1):
                    if sensor['id'] not in ignored_devices:
                        if 'class' in sensor and sensor['class'] == 'kube':
                            sensor['name'] = kube_config[str(sensor['kid'])]['name']
                            if 'type' in sensor and (sensor['type'] == 'movement' or sensor['type'] == 'vibration'):
                                binary_sensors.append(sensor)
                            elif 'type' in sensor and sensor['type'] == 'proximity':
                                _LOGGER.debug('Ignoring proximity sensor: %s', sensor['name'])
                            elif 'type' in sensor and sensor['type'] == 'vibration':
                                binary_sensors.append(sensor)
                            else:
                                sensors.append(sensor)
                        else:
                            if 'port' in sensor:
                                sensor['name'] = flx_config[str(sensor['port'][0])]['name']
                            sensors.append(sensor)

            hass.data[FLUKSO_CLIENT] = client
            hass.data[FLUKSO_CLIENT].unsubscribe("/device/+/config/sensor")
            hass.data[FLUKSO_CLIENT].subscribe("/sensor/+/+")
            _LOGGER.debug('Loading platforms')
            load_platform(hass, 'sensor', DOMAIN, sensors)
            load_platform(hass, 'binary_sensor', DOMAIN, binary_sensors)
            _LOGGER.debug('Done loading platforms')
            # client.loop_stop()
            # client.disconnect()
        elif conftype == "flx":
            flx_config = json.loads(msg.payload)
            client.unsubscribe("/device/+/config/flx")
            client.subscribe("/device/+/config/kube")
        elif conftype == "kube":
            kube_config = json.loads(msg.payload)
            client.unsubscribe("/device/+/config/kube")
            client.subscribe("/device/+/config/sensor")
        else:
            _LOGGER.warning('unknown config type: %s', conftype)

    @asyncio.coroutine
    def connect():
        _LOGGER.debug('Connecting to Flukso Mqtt broker and listening for config messages')
        # subscribe to topics /device/+/config/+
        # connect to flukso Mqtt broker
        mqttc.on_connect = on_connect
        mqttc.on_message = on_message
        mqttc.enable_logger(_LOGGER)
        mqttc.connect(host, port=port, keepalive=keepalive)
        mqttc.loop_start()
        _LOGGER.debug('Connected Flukso broker')

    hass.async_add_job(connect)
    return True
