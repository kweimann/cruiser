import logging
import pprint
import sys
import time
import traceback

import requests


class Listener:
    def notify(self, log): pass
    def notify_exception(self, exc_info=None): pass


class TelegramListener(Listener):
    def __init__(self, chat_id, api_token):
        self.chat_id = chat_id
        self.api_token = api_token

    def notify(self, log):
        name = log.get('log_name', None)
        if name == 'scheduled_escape':
            origin = log['origin']
            hostile_arrival = time.ctime(log['hostile_arrival'])
            escape_time = time.ctime(log['escape_time'])
            message = f'Hostile fleet attacking `{origin}` on `{hostile_arrival}`. ' \
                      f'Scheduled escape on `{escape_time}`.'
        elif name == 'return_flight':
            error = log.get('error', None)
            origin = log['fleet'].origin
            dest = log['fleet'].dest
            hostile_arrival = time.ctime(log['hostile_arrival'])
            if error:
                message = f'Failed to recall fleet back to `{origin}` ' \
                          f'due to attack on `{dest}` on `{hostile_arrival}`: `{error}`'
            else:
                message = f'Recalled fleet back to `{origin}` ' \
                          f'due to attack on `{dest}` on `{hostile_arrival}`.'
        elif name == 'escape_attack':
            error = log.get('error', None)
            origin = log['origin']
            hostile_arrival = time.ctime(log['hostile_arrival'])
            if error:
                message = f'Failed to save fleet from an attack on `{origin}` on `{hostile_arrival}`: {error}'
            else:
                message = f'Fleet escaped from an attack on `{origin}` on `{hostile_arrival}`.'
        else:
            if name:
                logging.warning(f'Unknown log `{name}`: {log}')
            else:
                logging.warning(f'Unknown log: {log}')
            message = f'`{pprint.pformat(log)}`'
        message = self._escape_markdown_string(message)
        self._send_message(message, parse_mode='MarkdownV2')

    def notify_exception(self, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()
        exc_type, exc_value, tb = exc_info
        exc_string = ''.join(traceback.format_exception(exc_type, exc_value, tb))
        message = f'Exception occurred: {exc_type.__name__}: {exc_value}\n{exc_string}'
        self._send_message(message)

    def _send_message(self, message, **kwargs):
        try:
            response = requests.get(
                self._send_message_url,
                timeout=5,
                params={'chat_id': self.chat_id, 'text': message, **kwargs})
            response = response.json()
            if not response['ok']:
                logging.error(f'Failed to send telegram message: {response["description"]}')
        except requests.exceptions.RequestException:
            logging.exception('Exception thrown while sending a telegram message.')

    @staticmethod
    def _escape_markdown_string(string):
        for c in '_[]()~>#+-=|{}.!':
            string = string.replace(c, f'\\{c}')
        return string

    @property
    def _send_message_url(self):
        return f'{self._api_url}/sendMessage'

    @property
    def _api_url(self):
        return f'https://api.telegram.org/bot{self.api_token}'
