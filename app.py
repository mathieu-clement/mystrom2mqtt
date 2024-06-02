#!/usr/bin/env python3

import ischedule
import logging
import os
import paho.mqtt.client as mqtt
import sys

# Local packages
from scheduler import Scheduler
from switch import Switch



class App:
    """
    This MQTT Subscriber subscribes to the MQTT /relay/command topic, listening for either the `on` or `off` payloads,
    and subsequently make an HTTP request to the Switch itself to execute the state change.
    """

    def __init__(self, devices, broker, port=1883, username='', password=''):
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

        user : string, optional
            Username to authenticate to MQTT

        password : string, optional
            Password to authenticate to MQTT
        """

        self.devices = devices  
        # verify device identifier does not contain slashes
        for device in self.devices:
            if '/' in device.identifier:
                raise Exception('Device identifiers may not contain forward slashes (/) but "%s" does' % (device.identifier,))
        self.devices_map = {device.identifier : device for device in devices}

        self.mqtt_client = mqtt.Client('mystrom2mqtt')
        if username != '' and password != '':
            logging.info('Using MQTT with authentication')
            self.mqtt_client.username_pw_set(username, password)
        else:
            logging.info('Using MQTT without authentication')
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
            device.refresh_report()
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


    def refresh_all_devices(self):
        for device in self.devices:
            was_on_before = device.is_on
            
            device.refresh_report()
            
            was_on_after = device.is_on

            if was_on_before != was_on_after:
                self.publish_new_state(device)



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

    # BROKER environment variable
    # specifies the broker IP address or hostname. See App.__init__ pydoc for more information if you wish to set a different port
    # than the default (1883).
    broker = os.environ['BROKER']

    # MQTT_USER environment variable
    # specifies the username to connect to MQTT broker
    mqtt_user = os.environ['MQTT_USER']
    
    # MQTT_PASSWORD environment variable
    # specifies the password to connect to MQTT broker
    mqtt_password = os.environ['MQTT_PASSWORD']
    
    app = App(switches, broker, 1883, mqtt_user, mqtt_password)

    # POLLING_PERIOD environment variable, in seconds. Disabled by default.
    # This controls how often the "/report" is fetched to update the device state.
    # In practice, I would set this no shorter than 60 seconds, unless this information is used for an automation, in which case
    # myStrom is probably the wrong tool for the job, you need a smart plug with webhook or MQTT capability out-of-the-box.
    # The main purposes are tracking physical button presses and reading sensors (power usage and temperature).
    polling_period = int(os.environ['POLLING_PERIOD'] if 'POLLING_PERIOD' in os.environ else -1)
    if polling_period > 0:
        Scheduler().run_periodically(target=app.refresh_all_devices, period=float(polling_period))

    # To test this app, you can use mosquitto_pub and mosquitto_sub. For example:
    # mosquitto_sub -h 192.168.0.2 -t 'mystrom/A4CF12FA3802/relay'
    # mosquitto_pub -h 192.168.0.2 -t 'mystrom/A4CF12FA3802/relay/command' -m 'on' 

    app.loop_forever()
