import asyncio
import logging.config

import yaml

from bot import OGameBot
from bot.eventloop import Scheduler
from ogame.client import OGame


def load_yaml(file):
    with open(file) as fh:
        return yaml.safe_load(fh)


if __name__ == '__main__':
    logging_config = load_yaml('logging.yaml')
    client_config = load_yaml('client.yaml')
    account_config = client_config['account']

    logging.config.dictConfig(logging_config)

    client = OGame(universe=account_config['universe'],
                   username=account_config['username'],
                   password=account_config['password'],
                   language=account_config['language'])

    scheduler = Scheduler()

    bot = OGameBot(client, scheduler)

    loop = asyncio.get_event_loop()

    try:
        bot.start()
        loop.run_until_complete(scheduler.main_loop(bot.handle_event))
    except:
        logging.exception("Exception thrown in the __main__")
        raise
