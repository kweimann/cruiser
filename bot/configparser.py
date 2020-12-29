import logging

import requests
import yaml

from bot.listeners import TelegramListener, DiscordListener, AlertListener
from bot.protocol import SendExpedition
from ogame.game.const import Ship, CoordsType, Resource
from ogame.game.model import Coordinates
from ogame.util import find_unique


def parse_bot_config(config):
    """ @return Parameters to initialize OGameBot. """
    bot_config = config.get('bot', {})
    sleep_min = bot_config.get('sleep_min')
    sleep_max = bot_config.get('sleep_max')
    min_time_before_attack_to_act = bot_config.get('min_time_before_attack_to_act')
    max_time_before_attack_to_act = bot_config.get('max_time_before_attack_to_act')
    try_recalling_saved_fleet = bot_config.get('try_recalling_saved_fleet')
    max_return_flight_time = bot_config.get('max_return_flight_time')
    harvest_expedition_debris = bot_config.get('harvest_expedition_debris')
    harvest_speed = bot_config.get('harvest_speed')
    return _remove_empty_values({
        'sleep_min': sleep_min,
        'sleep_max': sleep_max,
        'min_time_before_attack_to_act': min_time_before_attack_to_act,
        'max_time_before_attack_to_act': max_time_before_attack_to_act,
        'try_recalling_saved_fleet': try_recalling_saved_fleet,
        'max_return_flight_time': max_return_flight_time,
        'harvest_expedition_debris': harvest_expedition_debris,
        'harvest_speed': harvest_speed
    })


def parse_client_config(config):
    """ @return Parameters to initialize OGame client. """
    # Parse account information.
    account_config = _require('account', config)
    username = _require('username', account_config)
    password = _require('password', account_config)
    universe = _require('universe', account_config)
    language = _require('language', account_config)
    country = _require('country', account_config)
    if isinstance(universe, int):  # universe is server number
        server_number = universe
    else:  # universe is server name so we have to find the corresponding number
        servers = get_servers(timeout=10)
        def get_server_data(data): return data['name'].casefold(), data['language'].casefold()
        server = find_unique(
            item=(universe.casefold(), language.casefold()),
            iterable=servers,
            key=get_server_data)
        if not server:
            raise ValueError(f'Failed to match {universe} ({language}) to any server.')
        server_number = server['number']
        logging.debug(f'Matched {universe} ({language}) to server {server_number}.')
    variations = {"us": "en"}
    if language in variations:
        locale = f'{variations[language]}_{country}'
    else:
        locale = f'{language}_{country}'
    # Parse client parameters
    bot_config = config.get('bot', {})
    request_timeout = bot_config.get('request_timeout')
    delay_between_requests = bot_config.get('delay_between_requests')
    return _remove_empty_values({
        'username': username,
        'password': password,
        'language': language,
        'server_number': server_number,
        'locale': locale,
        'request_timeout': request_timeout,
        'delay_between_requests': delay_between_requests
    })


def parse_listener_config(config):
    """ @return List of listeners. """
    bot_config = config.get('bot', {})
    listeners_config = config.get('listeners', {})
    active_listeners = bot_config.get('listeners', [])
    listeners = [_initialize_listener(name, listeners_config.get(name))
                 for name in active_listeners]
    return listeners


def parse_expedition_config(config):
    """ @return List of expeditions. """
    bot_config = config.get('bot', {})
    expeditions_config = config.get('expeditions', {})
    active_expeditions = bot_config.get('expeditions', [])
    expeditions = [_initialize_expedition(id, expeditions_config.get(id))
                   for id in active_expeditions]
    return expeditions


def get_servers(**kwargs):
    """ @return List of all available servers. We use it for matching server name with its number. """
    return requests.get('https://lobby.ogame.gameforge.com/api/servers', **kwargs).json()


def load_config(file):
    """ Load configuration from yaml file. """
    with open(file, 'r') as stream:
        return yaml.safe_load(stream)


def _initialize_listener(name, config):
    if name == 'telegram':
        return TelegramListener(**config)
    elif name == 'discord':
        return DiscordListener(**config)
    elif name == 'alert':
        return AlertListener(**config)
    else:
        raise ValueError(f'Unknown listener: {name}')


def _initialize_expedition(id, config):
    origin_galaxy, origin_system, origin_position = _require('origin', config)
    origin_type_name = config.get('origin_type', 'planet')
    origin_type = CoordsType.from_name(origin_type_name)
    if not origin_type:
        raise ValueError(f'Unknown origin type: {origin_type_name}')
    dest_galaxy, dest_system, dest_position = config.get('dest', [origin_galaxy, origin_system, 16])
    ships = {}
    for ship_name, amount in _require('ships', config).items():
        ship = Ship.from_name(ship_name)
        if not ship:
            raise ValueError(f'Unknown ship: {ship_name}')
        ships[ship] = amount
    cargo = {}
    for resource_name, amount in config.get('cargo', {}).items():
        resource = Resource.from_name(resource_name)
        if not resource:
            raise ValueError(f'Unknown resource: {resource_name}')
        cargo[resource] = amount
    speed = config.get('speed', 10)
    holding_time = config.get('holding_time', 1)
    repeat = config.get('repeat', 'forever')
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
        id=id,
        origin=origin,
        dest=dest,
        ships=ships,
        speed=speed,
        holding_time=holding_time,
        repeat=repeat,
        cargo=cargo)
    return expedition


def _require(key, cfg, error_msg=None):
    """ Ensures that `key` is in the config `cfg`. """
    error_msg = error_msg or f'Missing field `{key}` in the config file.'
    val = cfg.get(key)
    if not val:
        raise ValueError(error_msg)
    return val


def _remove_empty_values(dictionary):
    """ Remove None values from a dictionary. """
    return {k: v for k, v in dictionary.items() if v is not None}
