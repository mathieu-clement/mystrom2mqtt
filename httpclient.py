#!/usr/bin/env python3

import logging
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

