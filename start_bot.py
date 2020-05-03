import argparse
import asyncio
import logging.config

import yaml

from bot import (
    OGameBot,
    Scheduler
)
from bot.listeners import TelegramListener

from ogame import OGame


def load_yaml(file):
    return yaml.safe_load(open(file))


def load_listeners(config):
    listeners = {'telegram': TelegramListener}
    listeners = [listeners[listener](**config['listeners'][listener])
                 for listener in config['bot']['listeners'] if listener in listeners]
    return listeners


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, default='config.yaml', help='Path to the config file.')
    args = parser.parse_args()

    logging.config.dictConfig(load_yaml('logging.yaml'))
    logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)

    logging.debug('Loaded config from %s', args.config)
    config = load_yaml(args.config)
    account = config['account']
    request_timeout = config['bot'].pop('request_timeout', 10)

    client = OGame(universe=account['universe'],
                   username=account['username'],
                   password=account['password'],
                   language=account['language'],
                   request_timeout=request_timeout)

    scheduler = Scheduler()
    bot = OGameBot(client, scheduler, **config['bot'])

    listeners = load_listeners(config)
    for listener in listeners:
        bot.add_listener(listener)
        logging.debug('Added listener: %s', type(listener).__name__)

    loop = asyncio.get_event_loop()

    try:
        bot.start()
        loop.run_until_complete(scheduler.main_loop(bot.handle_event))
    except Exception:
        logging.exception("Exception thrown in the __main__")
        raise
