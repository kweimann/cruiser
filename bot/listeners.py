import logging
import sys

import requests

from bot.protocol import (
    NotifyEscapeScheduled,
    NotifyFleetRecalled,
    NotifyFleetEscaped,
    NotifyExpeditionFinished,
    NotifyExpeditionCancelled
)
from ogame.util import ftime


class Listener:
    def notify(self, log): pass
    def notify_exception(self, exc_info=None): pass


class TelegramListener(Listener):
    def __init__(self, chat_id, api_token):
        self.chat_id = chat_id
        self.api_token = api_token

    def notify(self, log):
        if isinstance(log, NotifyEscapeScheduled):
            message = f'Hostile fleet attacking `{log.planet}` on `{ftime(log.hostile_arrival)}`. ' \
                      f'Scheduled escape on `{ftime(log.escape_time)}`.'
        elif isinstance(log, NotifyFleetEscaped):
            if log.error:
                message = f'Failed to save fleet from an attack on `{log.origin}` ' \
                          f'on `{ftime(log.hostile_arrival)}`: `{log.error}`.'
            else:
                message = f'Fleet escaped from {log.origin} to {log.destination} ' \
                          f'due to an attack on `{ftime(log.hostile_arrival)}`.'
        elif isinstance(log, NotifyFleetRecalled):
            if log.error:
                message = f'Failed to recall fleet back to `{log.origin}` ' \
                          f'due to attack on `{log.destination}` on `{ftime(log.hostile_arrival)}`: `{log.error}`.'
            else:
                message = f'Recalled fleet back to `{log.origin}` ' \
                          f'due to attack on `{log.destination}` on `{ftime(log.hostile_arrival)}`.'
        elif isinstance(log, NotifyExpeditionFinished):
            if log.error:
                message = f'Expedition from {log.expedition.origin} had to be removed due to an error: `{log.error}`.'
            else:
                message = f'Expedition from {log.expedition.origin} finished successfully.'
        elif isinstance(log, NotifyExpeditionCancelled):
            if log.cancellation.return_fleet:
                if log.fleet_returned:
                    message = f'Expedition from {log.expedition.origin} has been cancelled and the fleet returned.'
                else:
                    message = f'Expedition from {log.expedition.origin} has been cancelled' \
                              f'but the fleet could not be returned.'
            else:
                message = f'Expedition from {log.expedition.origin} has been cancelled.'
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
        message = f'Exception occurred: {exc_type.__name__}: {exc_value}'
        self._send_message(message)

    def _send_message(self, message, **kwargs):
        try:
            response = requests.get(
                self._send_message_url,
                timeout=5,
                params={'chat_id': self.chat_id, 'text': message, **kwargs})
            response = response.json()
            if not response.get('ok'):
                logging.error(f'Failed to send telegram message: {response.get("description")}')
        except requests.exceptions.RequestException:
            logging.exception('Exception thrown while sending a telegram message.')
        except ValueError:
            logging.exception('Exception thrown while parsing the response.')

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
