#!/usr/bin/env python3

import json
import logging
import os
import paho.mqtt.client as mqtt
import subprocess


class HttpException(Exception):
    def __init__(self, message, exit_code, response=None):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.response = response


class HttpClient:
    """
    Some hosts (such as my Swisscom Home Switch) refuse anything with the "Accept-Encoding" header
    and I couldn't find a way to prevent the HTTP libraries in Python
    to send them.
    Curl, in comparison, does not send it by default.

    This is an http client that relies on curl to make requests.
    """

    def get(self, url):
        logging.debug('HTTP request: ' + url)
        process = subprocess.Popen(['curl', '--location', '--max-time', str(5), '-s', url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        response = stdout.decode('utf-8')
        logging.debug("Host response: " + response)
        logging.debug("curl return code: " + str(process.returncode))

        if process.returncode != 0:
            message = None
            if process.returncode == 7:
                message = "Failed to connect to host"
            elif process.returncode == 28:
                message = "The request timed out"
            elif process.returncode != 0:
                message = "curl exited with code " + str(process.returncode)

            raise HttpException(message, process.returncode, response)

        return response



class Switch:
    """
    A Switch that can be turned on or off
    """

    def __init__(self, identifier, host):
        """
        Parameters
        ----------
        identifier : string
            Identifier of the switch, typically the uppercase MAC address without colons (:)

        host: string
            the IP address or hostname
        """
        self.identifier = identifier
        self.host = host
        self.http_client = HttpClient()
        self._get_report()
        self._get_info()


    def turn_on(self):
        logging.info("Turning on " + str(self))
        self._change_state(1)


    def turn_off(self):
        logging.info("Turning off " + str(self))
        self._change_state(0)


    def refresh_report(self):
        logging.info("Refreshing state " + str(self))
        self._get_report()


    def _get_report(self):
        url = 'http://' + self.host + '/report'
        try:
            response = self.http_client.get(url)
            self.is_on = json.loads(response)['relay']
        except HttpException as e:
            logging.error(e.message)


    def refresh_info(self):
        logging.info("Refreshing info " + str(self))
        self._get_info()


    def _get_info(self):
        url = 'http://' + self.host + '/info'
        try:
            response = self.http_client.get(url)
            self.info = json.loads(response)
        except HttpException as e:
            logging.error(e.message)


    def _change_state(self, state):
        url = 'http://' + self.host + '/relay?state=' + str(state)
        try:
            self.http_client.get(url)
        except HttpException as e:
            logging.error(e.message)



    def __repr__(self):
        return "Switch('" + self.identifier + "','" + self.host + "')"


class App:
    """
    This MQTT Subscriber subscribes to the MQTT /relay/command topic, listening for either the `on` or `off` payloads,
    and subsequently make an HTTP request to the Switch itself to execute the state change.
    """

    def __init__(self, devices, broker, port=1883):
        """
        Connects to the MQTT broker, which will also trigger it to subscribe to the appropriate topics if successful.
        
        Parameters
        ----------
        devices : list
            a list of Switches to be turned on or off

        broker : string
            The broker hostname or IP address

        port : int, optional
            The port number of the broker. 1883 by default. 8883 (TLS) might work but it has not been tested.
        """

        self.devices = devices # TODO verify identifier does not contain slashes
        self.devices_map = {device.identifier : device for device in devices}

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        self.mqtt_client.connect(broker, port)


    def loop_forever(self):
        self.mqtt_client.loop_forever()


    def on_mqtt_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT with result code " + str(rc))
        
        topics = [('mystrom/' + device.identifier + '/relay/command', 2) for device in self.devices]
        self.mqtt_client.subscribe(topics)


    def on_mqtt_message(self, client, userdata, msg):
        logging.debug(msg.topic + ": " + str(msg.payload))

        topic_components = msg.topic.split('/')
        device_identifier = topic_components[1]

        payload = msg.payload.decode('utf-8')
        device = self.devices_map[device_identifier]

        if msg.topic.endswith('/relay/command'):
            self.on_relay_command_message(device, payload)
        else:
            logging.warning('No action defined for topic ' + msg.topic)


    def on_relay_command_message(self, device, payload):
        if payload == 'on':
            device.turn_on()
        elif payload == 'off':
            device.turn_off()
        elif payload == 'refresh':
            pass
        elif payload == 'announce':
            device.refresh_info()
            self.publish_new_info(device)
        else:
            logging.warning("Unknown payload: " + payload)

        device.refresh_report()
        self.publish_new_state(device)


    def publish_new_state(self, device):
        payload = 'on' if device.is_on else 'off'
        topic = 'mystrom/' + device.identifier + '/relay'
        self.mqtt_client.publish(topic, payload=payload, retain=True)
    

    def publish_new_info(self, device):
        payload = json.dumps(device.info)
        topic = 'mystrom/' + device.identifier + '/info'
        self.mqtt_client.publish(topic, payload=payload, retain=False)



if __name__ == '__main__':
    level = logging.INFO
    if 'LOG_LEVEL' in os.environ:
        if os.environ['LOG_LEVEL'] == 'DEBUG':
            level = logging.DEBUG
        elif os.environ['LOG_LEVEL'] == 'INFO':
            level = logging.INFO
        elif os.environ['LOG_LEVEL'] == 'WARN':
            level = logging.WARN
        else:
            raise Exception('Unknown log level: ' + os.environ['LOG_LEVEL'])
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=level)

    # SWITCHES environment variable
    # contains a comma-separated list of switches. Each switch is represented by its MAC address (or any other identifier)
    # and its IP address or hostname separated by a colon.
    # For example: 
    #   SWITCHES="A4CF12FA3802:192.168.0.25,C82B9627CD8A:192.168.0.26"
    switches = []
    for switch in os.environ['SWITCHES'].split(','):
        identifier, host = switch.split(':')
        switches.append(Switch(identifier, host))

    # BROKER environment variables
    # specifies the broker IP address or hostname. See App.__init__ pydoc for more information if you wish to set a different port
    # than the default (1883).
    broker = os.environ['BROKER']

    # To test this app, you can use mosquitto_pub and mosquitto_sub. For example:
    # mosquitto_sub -h 192.168.0.2 -t 'mystrom/A4CF12FA3802/relay'
    # mosquitto_pub -h 192.168.0.2 -t 'mystrom/A4CF12FA3802/relay/command' -m 'on' 

    app = App(switches, broker)
    app.loop_forever()
