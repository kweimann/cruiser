import logging
import sys
import time
import traceback

import requests

from bot.protocol import (
    NotifyEscapeScheduled,
    NotifyFleetRecalled,
    NotifyFleetEscaped
)


class Listener:
    def notify(self, log): pass
    def notify_exception(self, exc_info=None): pass


class TelegramListener(Listener):
    def __init__(self, chat_id, api_token):
        self.chat_id = chat_id
        self.api_token = api_token

    def notify(self, log):
        if isinstance(log, NotifyEscapeScheduled):
            hostile_arrival = time.ctime(log.hostile_arrival)
            escape_time = time.ctime(log.escape_time)
            message = f'Hostile fleet attacking `{log.planet}` on `{hostile_arrival}`. ' \
                      f'Scheduled escape on `{escape_time}`.'
        elif isinstance(log, NotifyFleetEscaped):
            hostile_arrival = time.ctime(log.hostile_arrival)
            if log.error:
                message = f'Failed to save fleet from an attack on `{log.origin}` ' \
                          f'on `{hostile_arrival}`: {log.error}'
            else:
                message = f'Fleet escaped from {log.origin} to {log.destination} ' \
                          f'due to an attack on `{hostile_arrival}`.'
        elif isinstance(log, NotifyFleetRecalled):
            hostile_arrival = time.ctime(log.hostile_arrival)
            if log.error:
                message = f'Failed to recall fleet back to `{log.origin}` ' \
                          f'due to attack on `{log.destination}` on `{hostile_arrival}`: `{log.error}`'
            else:
                message = f'Recalled fleet back to `{log.origin}` ' \
                          f'due to attack on `{log.destination}` on `{hostile_arrival}`.'
        else:
            logging.warning(f'Unknown log: {log}')
            message = None
        if message:
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
