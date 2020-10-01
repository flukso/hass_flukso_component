### Installation
Put the files in this repo in your [custom_components folder](https://developers.home-assistant.io/docs/creating_integration_file_structure#where-home-assistant-looks-for-integrations) and add the following to your configuration.yaml file:

```
flukso:
  ignore_sensors:
    - 0123456789abcdef0123456789abcdef
```

If you want to see the debug messages in your home assistant logs, configure the logger as follows:
```
logger:
  default: warning
  logs:
    custom_components.flukso: debug
```

Then, set up a MQTT bridge between you Home Assistant MQTT broker and your Flukso's MQTT broker. Here is an example bridge config:
```
connection flukso01
address <flukso ip>:1883
remote_clientid flukso01bridge
cleansession true
restart_timeout 5
topic # in 0
```

### TODO:
* Integrate in HA source code and add autodiscovery
* Add support for multiple Flukso's
