import argparse
import asyncio
import logging.config

from bot import (
    OGameBot,
    Scheduler
)
from bot.configparser import (
    load_config,
    parse_client_config,
    parse_bot_config,
    parse_listener_config,
    parse_expedition_config
)
from ogame import OGame

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, default='config.yaml', help='Path to the config file.')
    args = parser.parse_args()

    logging.config.dictConfig(load_config('logging.yaml'))
    logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)

    try:
        # load configuration from yaml file
        config = load_config(args.config)
        client_params = parse_client_config(config)
        bot_params = parse_bot_config(config)
        listeners = parse_listener_config(config)
        expeditions = parse_expedition_config(config)

        logging.debug('Loaded config from %s', args.config)

        # Scheduler notifies Cruiser about any new events
        #  (e.g. when it's time to defend a planet!).
        scheduler = Scheduler()

        # Client controls the account. It provides an interface to
        #  download and parse information from the OGame server as well as
        #  send commands to the servers.
        client = OGame(**client_params)

        # Cruiser makes the decisions. It receives events from the scheduler
        #  and acts accordingly. It's decision making is based on the
        #  information the client provides.
        bot = OGameBot(client, scheduler, **bot_params)

        # Add listeners (e.g. Telegram) that will notify users about
        #  important events (e.g. planet under attack).
        for listener in listeners:
            bot.add_listener(listener)
            logging.debug('Added listener: %s', type(listener).__name__)

        # Schedule expeditions if they were defined.
        for expedition in expeditions:
            scheduler.push(
                delay=0,
                priority=0,
                data=expedition)

        # Login into the game. From now on the client will handle
        #  any subsequent logins in case of a logout.
        #
        #  This means you are free to access your account from the
        #  browser and Cruiser will simply relogin if it is awake.
        client.login()

        # Initialize Cruiser's interval state.
        bot.start()

        # Run the scheduler indefinitely.
        # This will wake up Cruiser for the first time.
        asyncio.run(scheduler.main_loop(bot.handle_work))

    except Exception:
        logging.exception("Exception thrown in the __main__")
        raise
