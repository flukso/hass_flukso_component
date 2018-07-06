### Installation
Put the files in this repo in your [custom_components folder](https://developers.home-assistant.io/docs/en/creating_component_loading.html) and add the following to your configuration.yaml file:

```
flukso:
  host: my.flukso.ip
  ignore_devices:
    - 0123456789abcdef0123456789abcdef
```
If you want to see the debug messages in your home assistant logs, configure the logger as follows:
```
logger:
  default: warning
  logs:
    custom_components.flukso: debug
    custom_components.sensor.flukso: debug
    custom_components.binary_sensor.flukso: debug
```

### TODO:
* See if we are satisfied with the current unique id. Currently, the id is [sensor type].[name]_[sensor hash] Maybe add the flukso id as well?
* Integrate in HA source code and add autodiscovery
* Add support for multiple Flukso's