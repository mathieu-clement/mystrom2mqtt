# MQTT proxy for myStrom Switches

UPDATE: For Button and Button+, I recommend [this project](https://github.com/home-assistant-ecosystem/mystrom2mqtt) instead.

## What is this?

This application acts as a proxy between an MQTT client and a Swisscom Home / myStrom Smart Switch or button. The switches do not support MQTT out-of-the-box and
I'm not aware of any firmware that can be flashed to make it support it (e.g. Tasmota).

In the mean time, this proxy will subscribe to a topic that a smart home platform such as Home Assistant can publish to to send commands
(e.g. relay on or off), and it will publish to a topic that HA can subscribe to to receive updates from the device (e.g. state of the relay).

## Initial setup of Swisscom Home Smart Switch

Please see my other repository (swisscom-switch-to-mystrom) to set up a Swisscom Home smart switch without the Swisscom Home app and a Swisscom
Internet Box.

## Running with Docker

The best and easiest way to use this software is through Docker. Use the `mathieuclement/mystrom2mqtt` image on Docker hub. It is recommended to run the container in Bridge mode. And there's no need to expose any ports, hooray!

The following environment variables must be defined:

| Variable | Description | Example |
| -------- | ----------- | ------- |
| `SWITCHES` | Identifier and IP address / hostname of each switch, <br/> typically the MAC address in uppercase without colons is used as the identifier <br/> Identifier and host are separated with a colon. <br/> Switches are separated by a comma. | `A4CF12FA3802:192.168.0.25` <br/> `C82B9627CD8A:pendant.local` |
| `BROKER` | IP address / hostname of MQTT broker <br/> Only the default port (1883) is supported at the moment. | `mqtt-broker.local`

The `./docker-run.sh` shows how you can run this container (you might need to run `docker pull` the first time).

## Home Assistant Configuration

### MQTT installation

We'll use the MQTT integration (you'll have to install it first and configure it to talk to your broker). 

### Add your switches

Define the following in your `configuration.yaml`:

```yaml
mqtt:
  light:
    - name: "Pendant"
      unique_id: "mystrom_pendant"
      icon: "mdi:lamp"
      payload_on: "on"
      payload_off: "off"
      qos: 2
      state_topic: "mystrom/A4CF12FA3802/relay"
      command_topic: "mystrom/A4CF12FA3802/relay/command"
      json_attributes_topic: "mystrom/A4CF12FA3802/info"
  
  switch:
    - name: "Hi-Fi"
      unique_id: "mystrom_hifi"
      icon: "mdi:speaker-wireless"
      payload_on: "on"
      payload_off: "off"
      qos: 2
      state_topic: "mystrom/C82B9627CD8A/relay"
      command_topic: "mystrom/C82B9627CD8A/relay/command"
      json_attributes_topic: "mystrom/C82B9627CD8A/info"
```

Note that I've defined the name and icon in YAML, but you can do it in the UI later.

Restart Home Assistant. Then head to the "Integrations" page and you should see two new entities in MQTT.

### Refresh entity attributes

You can use the "Configure" page of the MQTT integration in Home Assistant to send the following message:

```
topic: mystrom/C82B9627CD8A/relay/command
payload: announce
```

This will refresh the attributes of that particular entity ("C82B9627CD8A").

You can also listen to the topic `/mystrom/C82B9627CD8A/info` to see the result, or just inspect the entity and look at the attributes.

Please note that this is entirely **optional**. There's no purpose to this but to geek out and check some of the device settings. It could be useful to find out the IP address from within HA or check the Wi-Fi signal strength.

## Setting up the web hook on switches

**Unfortunately the web hook doesn't appear to get triggered even after being set!** (tested on Swisscom Home smart switch)

So here's the workaround we'll use to get around this limitation:

  - Query the state after making the request to change it. This is what the Home Assistant mystrom integration does by the way. 
    It's not super useful for the Swisscom Home switch since it doesn't have extra sensors, but on devices that support them, this gives us a chance to update them.
  - Polling: to detect when the physical button on the switch is pressed or when the switch is triggered from other applications

### Environment variables (Polling)

| Environment variable | Description | Sample value |
| -------------------- | ----------- | ------------ |
| `POLLING_PERIOD` | How often to ping the device (in seconds) <br/> Set to `-1` to disable. | `60` |


### Swisscom Home Switch

On the Swisscom Home Smart Switch, you would set it up like this:

```
curl --request POST "http://192.168.0.101/api/v1/action/button" \
--header 'Content-Type: text/plain' \
--data-raw 'http://192.168.0.15:5010/webhooks/button'
```


### myStrom Switch

Untested at this time. You probably want `/api/v1/action/relay`. The `GET` returns a payload like this:

```json
{
	"on": "",
	"off": "",
	"url": ""
}
```

instead of only `url` on the Swisscom Home switch.

## Supported devices

  - myStrom Switch (only to turn on / off and report the state of the relay at the moment,
    power and temperature measurements are a work in progress)
  - Swisscom Home Switch (the device itself lacks power and temperature measurements)
  - ~~myStrom Button~~ See note above

There is visibly an older version of the myStrom switch. I can't confirm if it supports the same features as the second version.
The same goes for the EU version (I have the CH version).

Similarly, there is a "Button+" but I have only tested the regular Button.

## Topics

### Prefix
 `/mystrom/<deviceId>`
 
 so when you see `/relay` the topic name really is `/mystrom/<deviceId>/relay`.

### Switches

| Topic            | Purpose           | Payload         |  
| ---------------- | ----------------- | --------------- | 
| `/relay`         | to query state    | `on` or `off`   |
| `/relay/command` | to turn on or off, or to refresh state | `on`, `off`, `refresh`, or `announce`   |
| `/info`          | to return data about the device | all data reported by `/api/v1/info` (HTTP)  <br/> e.g. MAC / IP addresses, WiFi SSID and signal strength |

`refresh` will query `/report` (switch state, temperature, power usage) which will publish to `/relay`, and `announce` will query `/info` which will publish to `/info`.


## Where to find the `<deviceId>`

```curl http://192.168.0.101/api/v1/info | jq .mac``` 

where 192.168.0.101 is the IP address of your device. Check your router or scan
your network with nmap to find it. In other words it's the MAC address in uppercase without colons (`:`), e.g. `A4CF1291NAF1`.
