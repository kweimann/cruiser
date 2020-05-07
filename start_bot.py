import argparse
import asyncio
import logging
import logging.config

import yaml

from bot import (
    OGameBot,
    Scheduler
)
from bot.listeners import TelegramListener
from bot.protocol import SendExpedition
from ogame import OGame
from ogame.game.const import Ship, CoordsType
from ogame.game.model import Coordinates


def main(args):
    config = load_config(args.config)
    logging.debug('Loaded config from %s', args.config)

    scheduler = Scheduler()
    loop = asyncio.get_event_loop()
    client = OGame(**config['client'])
    bot = OGameBot(client, scheduler, **config['bot'])

    for listener in config['listeners']:
        bot.add_listener(listener)
        logging.debug('Added listener: %s', type(listener).__name__)

    for expedition in config['expeditions']:
        scheduler.push(
            delay=0,
            priority=0,
            data=expedition)

    try:
        bot.start()
        loop.run_until_complete(scheduler.main_loop(bot.handle_work))
    except Exception:
        logging.exception("Exception thrown in the __main__")
        raise


def load_config(file: str):
    config = load_yaml(file)
    account_config = config.get('account')
    if not account_config:
        logging.error('Missing account settings in the config file.')
        raise ValueError('Missing account settings in the config file.')
    bot_config = config.get('bot', {})
    client_params = {
        'universe': account_config['universe'],
        'username': account_config['username'],
        'password': account_config['password'],
        'language': account_config['language'],
        'request_timeout': bot_config.get('request_timeout', 10),
        'delay_between_requests': bot_config.get('delay_between_requests', 0.5)}
    bot_params = {
        'sleep_min': bot_config.get('sleep_min', 10 * 60),
        'sleep_max': bot_config.get('sleep_max', 15 * 60),
        'min_time_before_attack_to_act': bot_config.get('min_time_before_attack_to_act', 2 * 60),
        'max_time_before_attack_to_act': bot_config.get('max_time_before_attack_to_act', 3 * 60)
    }
    listeners = [load_listener(listener_name, listener_config)
                 for listener_name, listener_config in config.get('listeners', {}).items()
                 if listener_name in bot_config.get('listeners', [])]
    expeditions = [load_expedition(expedition_id, expedition_config)
                   for expedition_id, expedition_config in config.get('expeditions', {}).items()
                   if expedition_id in bot_config.get('expeditions', [])]
    return {'client': client_params,
            'bot': bot_params,
            'listeners': listeners,
            'expeditions': expeditions}


def load_listener(listener_name, listener_config):
    if listener_name == 'telegram':
        return TelegramListener(**listener_config)
    else:
        raise ValueError(f'Unknown listener: {listener_name}')


def load_expedition(expedition_id, expedition_config):
    origin_galaxy, origin_system, origin_position = expedition_config['origin']
    origin_type = CoordsType.from_name(expedition_config.get('origin_type', 'planet'))
    dest_galaxy, dest_system, dest_position = expedition_config.get('dest', [origin_galaxy, origin_system, 16])
    ships = {Ship.from_name(ship): amount for ship, amount in expedition_config['ships'].items()}
    holding_time = expedition_config.get('holding_time', 1)
    repeat = expedition_config.get('repeat', 'forever')
    origin = Coordinates(
        galaxy=origin_galaxy,
        system=origin_system,
        position=origin_position,
        type=origin_type)
    dest = Coordinates(
        galaxy=dest_galaxy,
        system=dest_system,
        position=dest_position,
        type=CoordsType.planet)
    expedition = SendExpedition(
        id=expedition_id,
        origin=origin,
        dest=dest,
        ships=ships,
        holding_time=holding_time,
        repeat=repeat)
    return expedition


def load_yaml(file):
    with open(file, 'r') as stream:
        return yaml.safe_load(stream)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, default='config.yaml', help='Path to the config file.')
    args = parser.parse_args()

    logging.config.dictConfig(load_yaml('logging.yaml'))
    logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)

    main(args)
