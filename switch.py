#!/usr/bin/env python3

import json
import logging

from httpclient import HttpClient, HttpException


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
        self.is_on = None
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


