import functools
import logging
import time
from typing import List, Union, Dict
from urllib.parse import urlparse

import requests

from ogame.api.client import OGameAPI
from ogame.game.const import (
    Mission,
    CoordsType,
    Resource,
    Ship,
    Technology,
    CharacterClass
)
from ogame.game.model import (
    Coordinates,
    FleetEvent,
    Planet,
    FleetMovement,
    Production,
    Shipyard,
    Research,
    Resources,
    Movement,
    FleetDispatch,
    Overview
)
from ogame.util import (
    join_digits,
    parse_html,
    extract_numbers,
    str2bool,
    tuple2timestamp,
    find_first_between,
)


class NotLoggedInError(Exception):
    pass


class ParseException(Exception):
    pass


def keep_session(*, maxtries=1):
    def decorator_keep_session(func):
        @functools.wraps(func)
        def wrapper_keep_session(self, *args, **kwargs):
            tries = 0
            while True:
                try:
                    return func(self, *args, **kwargs)
                except NotLoggedInError:
                    if tries < maxtries:
                        self.login()
                        tries += 1
                    else:
                        raise
        return wrapper_keep_session
    return decorator_keep_session


class OGame:
    def __init__(self,
                 username: str,
                 password: str,
                 language: str,
                 server_number: int,
                 request_timeout: int = 10,
                 delay_between_requests: int = 0):
        self.username = username
        self.password = password
        self.language = language.casefold()
        self.server_number = server_number
        self.request_timeout = request_timeout
        self.delay_between_requests = delay_between_requests

        self._session = requests.session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/73.0.3683.103 '
                          'Safari/537.36'
        })

        self._account = None
        self._server_url = None
        self._tech_dictionary = None
        self._last_request_time = 0

    @property
    def api(self):
        return OGameAPI(
            server_number=self.server_number,
            server_language=self.language)

    def login(self) -> None:
        # Get PHPSESSID token used in every request.
        php_session_id = self._get_php_session_id()
        if not php_session_id:
            raise ValueError('Invalid credentials.')
        # Find the server.
        if not self._account:
            self._account = self._get_account()
            if not self._account:
                raise ValueError('Invalid server.')
        # Login to the server.
        login_response = self._request(
            method='get',
            url='https://lobby.ogame.gameforge.com/api/users/me/loginLink',
            delay=0,
            params={'id': self._account['id'],
                    'server[language]': self.language,
                    'server[number]': self.server_number})
        login_status = login_response.json()
        if 'error' in login_status:
            raise ValueError(login_status['error'])
        # Go to the landing page in the game.
        login_url = login_status['url']
        login_url_parsed = urlparse(login_url)
        self._server_url = login_url_parsed.netloc
        self._request(
            method='get',
            url=login_url,
            delay=0)
        # Initialize tech dictionary from the API. It is used for
        #  translating ship names while parsing the movement page.
        #  Note that we assume that the dictionary won't change.
        if self._tech_dictionary is None:
            self._tech_dictionary = self.api.get_localization()['technologies']

    def get_research(self,
                     delay: int = None) -> Research:
        research_soup = self._get_research(delay=delay)
        technology_elements = _find_at_least_one(research_soup, class_='technology')
        technologies = {}
        production = None
        for technology_el in technology_elements:
            level_el = _find_exactly_one(technology_el, class_='level')
            technology_id = int(technology_el['data-technology'])
            technology = Technology.from_id(technology_id)
            if not technology:
                logging.warning(f'Missing technology (id={technology_id})')
                continue
            level = int(level_el['data-value'])
            bonus = join_digits(level_el['data-bonus'])
            status = technology_el['data-status']
            if status == 'active':
                if production is not None:
                    logging.warning('Multiple productions encountered.')
                else:
                    prod_start = int(technology_el['data-start'])
                    prod_end = int(technology_el['data-end'])
                    production = Production(
                        o=technology,
                        start=prod_start,
                        end=prod_end)
            technologies[technology] = level + bonus
        return Research(
            technology=technologies,
            production=production)

    def get_shipyard(self,
                     planet: Union[Planet, int],
                     delay: int = None) -> Shipyard:
        shipyard_soup = self._get_shipyard(planet, delay=delay)
        ship_elements = _find_at_least_one(shipyard_soup, class_='technology')
        ships = {}
        production = None
        for ship_el in ship_elements:
            amount_el = _find_exactly_one(ship_el, class_='amount')
            ship_id = int(ship_el['data-technology'])
            ship = Ship.from_id(ship_id)
            if not ship:
                logging.warning(f'Missing ship (id={ship_id})')
                continue
            amount = int(amount_el['data-value'])
            status = ship_el['data-status']
            if status == 'active':
                if production is not None:
                    logging.warning('Multiple productions encountered.')
                else:
                    target_amount_el = _find_exactly_one(ship_el, class_='targetamount')
                    target_amount = int(target_amount_el['data-value'])
                    prod_start = int(ship_el['data-start'])
                    prod_end = int(ship_el['data-end'])
                    production = Production(
                        o=ship,
                        start=prod_start,
                        end=prod_end,
                        amount=target_amount - amount)
            ships[ship] = amount
        return Shipyard(
            ships=ships,
            production=production)

    def get_resources(self,
                      planet: Union[Planet, int]) -> Resources:
        def amount(res): return int(resources[res]['amount'])
        def storage(res): return int(resources[res]['storage'])
        resources = self._get_resources(
            planet=planet,
            delay=0)['resources']
        amounts = {Resource.metal: amount('metal'),
                   Resource.crystal: amount('crystal'),
                   Resource.deuterium: amount('deuterium'),
                   Resource.energy: amount('energy'),
                   Resource.dark_matter: amount('darkmatter')}
        storage = {Resource.metal: storage('metal'),
                   Resource.crystal: storage('crystal'),
                   Resource.deuterium: storage('deuterium')}
        return Resources(
            amount=amounts,
            storage=storage)

    def get_overview(self,
                     delay: int = None) -> Overview:
        overview_soup = self._get_overview(delay=delay)
        planet_list = overview_soup.find(id='planetList')
        smallplanets = planet_list.findAll(class_='smallplanet')
        character_class_el = overview_soup.find(id='characterclass').find('div')
        character_class = None
        if 'miner' in character_class_el['class']:
            character_class = CharacterClass.collector
        elif 'warrior' in character_class_el['class']:
            character_class = CharacterClass.general
        elif 'explorer' in character_class_el['class']:
            character_class = CharacterClass.discoverer
        planets = []
        for planet_div in smallplanets:
            planet_id = abs(join_digits(planet_div['id']))
            planet_name = planet_div.find(class_='planet-name').text.strip()
            galaxy, system, position = extract_numbers(planet_div.find(class_='planet-koords').text)
            planet_coords = Coordinates(galaxy, system, position, CoordsType.planet)
            planet = Planet(
                id=planet_id,
                name=planet_name,
                coords=planet_coords)
            planets.append(planet)
            moon_el = planet_div.find(class_='moonlink')
            if moon_el:
                moon_url = moon_el['href']
                moon_url_params = urlparse(moon_url).query.split('&')
                moon_id = join_digits(next(param for param in moon_url_params if 'cp' in param))
                moon_name = moon_el.img['alt']
                moon_coords = Coordinates(galaxy, system, position, CoordsType.moon)
                moon = Planet(
                    id=moon_id,
                    name=moon_name,
                    coords=moon_coords)
                planets.append(moon)
        return Overview(
            planets=planets,
            character_class=character_class)

    def get_events(self) -> List[FleetEvent]:
        event_list = self._get_event_list(delay=0)
        event_elements = event_list.findAll(class_='eventFleet')
        events = []
        for event_el in event_elements:
            if 'partnerInfo' in event_el['class']:
                # part of an ACS attack
                event_id = next(abs(join_digits(class_)) for class_ in event_el['class'] if 'union' in class_)
            else:
                event_id = abs(join_digits(event_el['id']))
            arrival_time = int(event_el['data-arrival-time'])
            return_flight = str2bool(event_el['data-return-flight'])
            mission = Mission(int(event_el['data-mission-type']))
            origin_galaxy, origin_system, origin_position = extract_numbers(event_el.find(class_='coordsOrigin').text)
            origin_type_el = event_el.find(class_='originFleet').find('figure')
            origin_type = self._parse_coords_type(origin_type_el)
            origin = Coordinates(origin_galaxy, origin_system, origin_position, origin_type)
            dest_galaxy, dest_system, dest_position = extract_numbers(event_el.find(class_='destCoords').text)
            dest_type_el = event_el.find(class_='destFleet').find('figure')
            dest_type = self._parse_coords_type(dest_type_el)
            dest = Coordinates(dest_galaxy, dest_system, dest_position, dest_type)
            player_id_el = event_el.find('a', class_='sendMail')
            player_id = int(player_id_el['data-playerid']) if player_id_el else None
            event = FleetEvent(
                id=event_id,
                origin=origin,
                dest=dest,
                arrival_time=arrival_time,
                mission=mission,
                return_flight=return_flight,
                player_id=player_id)
            events.append(event)
        return events

    def get_fleet_movement(self,
                           return_fleet: Union[FleetMovement, int] = None,
                           delay: int = None) -> Movement:
        def parse_fleet_info(fleet_info_el):
            def is_resource_cell(cell_index): return cell_index >= len(fleet_info_rows) - 3  # last 3 rows are resources
            def get_resource_from_cell(cell_index): return list(Resource)[3 - len(fleet_info_rows) + cell_index]
            fleet_info_rows = fleet_info_el.find_all(lambda el: _find_exactly_one(el, raise_exc=False, class_='value'))
            ships = {}
            cargo = {}
            for i, row in enumerate(fleet_info_rows):
                name_col, value_col = _find_exactly(row, n=2, name='td')
                amount = join_digits(value_col.text)
                if is_resource_cell(i):
                    resource = get_resource_from_cell(i)
                    cargo[resource] = amount
                else:
                    tech_name = name_col.text.strip()[:-1]  # remove colon at the end
                    tech_id = self._tech_dictionary.get(tech_name)
                    if not tech_id:
                        raise ParseException(f'Unknown ship (name={tech_name}) found while parsing.')
                    ship = Ship(tech_id)
                    ships[ship] = amount
            return ships, cargo

        movement_soup = self._get_movement(return_fleet, delay=delay)
        movement_el = movement_soup.find(id='movement')
        timestamp = int(movement_soup.find('meta', {'name': 'ogame-timestamp'})['content'])
        if not movement_el:
            # when there is no movement the server redirects to fleet dispatch
            slot_elements = movement_soup.find(id='slots').findAll('div', recursive=False)
            used_fleet_slots, max_fleet_slots = extract_numbers(slot_elements[0].text)
            used_expedition_slots, max_expedition_slots = extract_numbers(slot_elements[1].text)
            return Movement(
                fleets=[],
                used_fleet_slots=used_fleet_slots,
                max_fleet_slots=max_fleet_slots,
                used_expedition_slots=used_expedition_slots,
                max_expedition_slots=max_expedition_slots,
                timestamp=timestamp)
        else:
            fleet_slots_el = movement_el.find(class_='fleetSlots')
            expedition_slots_el = movement_el.find(class_='expSlots')
            fleet_details_elements = movement_el.findAll(class_='fleetDetails')
            used_fleet_slots, max_fleet_slots = extract_numbers(fleet_slots_el.text)
            used_expedition_slots, max_expedition_slots = extract_numbers(expedition_slots_el.text)
            fleets = []
            for fleet_details_el in fleet_details_elements:
                fleet_id = abs(join_digits(fleet_details_el['id']))
                arrival_time = int(fleet_details_el['data-arrival-time'])
                return_flight = str2bool(fleet_details_el['data-return-flight']) or False
                mission = Mission(int(fleet_details_el['data-mission-type']))
                origin_time = tuple2timestamp(extract_numbers(fleet_details_el.find(class_='origin').img['title']))
                dest_time = tuple2timestamp(extract_numbers(fleet_details_el.find(class_='destination').img['title']))
                if return_flight:
                    flight_duration = origin_time - dest_time
                    departure_time = dest_time - flight_duration
                else:
                    departure_time = origin_time
                end_time = int(fleet_details_el.find('span', class_='openDetails').a['data-end-time'])
                reversal_el = fleet_details_el.find('span', class_='reversal')
                if mission == Mission.expedition and not return_flight:
                    if not reversal_el:
                        # fleet is currently on expedition
                        holding = True
                        holding_time = end_time - departure_time
                    else:
                        # fleet is flying to expedition
                        holding = False
                        flight_duration = end_time - departure_time
                        holding_time = arrival_time - departure_time - 2 * flight_duration
                else:
                    holding = False
                    holding_time = 0
                origin_galaxy, origin_system, origin_position = extract_numbers(
                    fleet_details_el.find(class_='originCoords').text)
                origin_type_el = fleet_details_el.find(class_='originPlanet').find('figure')
                origin_type = self._parse_coords_type(origin_type_el)
                origin = Coordinates(origin_galaxy, origin_system, origin_position, origin_type)
                dest_galaxy, dest_system, dest_position = extract_numbers(
                    fleet_details_el.find(class_='destinationCoords').text)
                dest_type_el = fleet_details_el.find(class_='destinationPlanet').find('figure')
                if dest_type_el:
                    dest_type = self._parse_coords_type(dest_type_el)
                else:
                    # destination type is a planet by default
                    dest_type = CoordsType.planet
                dest = Coordinates(dest_galaxy, dest_system, dest_position, dest_type)
                fleet_info_el = _find_exactly_one(fleet_details_el, class_='fleetinfo')
                ships, cargo = parse_fleet_info(fleet_info_el)
                fleet = FleetMovement(
                    id=fleet_id,
                    origin=origin,
                    dest=dest,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    mission=mission,
                    return_flight=return_flight,
                    ships=ships,
                    cargo=cargo,
                    holding=holding,
                    holding_time=holding_time)
                fleets.append(fleet)
            return Movement(
                fleets=fleets,
                used_fleet_slots=used_fleet_slots,
                max_fleet_slots=max_fleet_slots,
                used_expedition_slots=used_expedition_slots,
                max_expedition_slots=max_expedition_slots,
                timestamp=timestamp)

    def get_fleet_dispatch(self,
                           planet: Union[Planet, int],
                           delay: int = None) -> FleetDispatch:
        fleet_dispatch_soup = self._get_fleet_dispatch(planet, delay=delay)
        token = find_first_between(str(fleet_dispatch_soup), left='fleetSendingToken = "', right='"')
        timestamp = int(fleet_dispatch_soup.find('meta', {'name': 'ogame-timestamp'})['content'])
        slot_elements = fleet_dispatch_soup.find(id='slots').findAll('div', recursive=False)
        used_fleet_slots, max_fleet_slots = extract_numbers(slot_elements[0].text)
        used_expedition_slots, max_expedition_slots = extract_numbers(slot_elements[1].text)
        ship_elements = fleet_dispatch_soup.findAll(class_='technology')
        ships = {}
        for ship_el in ship_elements:
            amount_el = _find_exactly_one(ship_el, class_='amount')
            ship_id = int(ship_el['data-technology'])
            ship = Ship.from_id(ship_id)
            if not ship:
                logging.warning(f'Missing ship (id={ship_id})')
                continue
            amount = int(amount_el['data-value'])
            ships[ship] = amount
        return FleetDispatch(
            dispatch_token=token,
            ships=ships,
            used_fleet_slots=used_fleet_slots,
            max_fleet_slots=max_fleet_slots,
            used_expedition_slots=used_expedition_slots,
            max_expedition_slots=max_expedition_slots,
            timestamp=timestamp)

    def send_fleet(self, *,
                   origin: Union[Planet, int],
                   dest: Union[Planet, Coordinates],
                   mission: Mission,
                   ships: Union[Dict[Ship, int], str] = 'all',
                   fleet_speed: int = 10,
                   resources: Dict[Resource, int] = None,
                   holding_time: int = None,
                   fleet_dispatch: FleetDispatch = None,
                   delay: int = None) -> FleetDispatch:
        """ @return: FleetDispatch before sending the fleet. """
        if isinstance(dest, Planet):
            dest = dest.coords
        if not resources:
            resources = {}
        if mission in [Mission.expedition, Mission.defend]:
            holding_time = holding_time or 1
        else:
            if holding_time is not None:
                logging.warning('Setting `holding_time` to 0')
            holding_time = 0
        if fleet_dispatch is None:
            fleet_dispatch = self.get_fleet_dispatch(origin, delay=delay)
        if ships == 'all':
            ships = fleet_dispatch.ships
        self._post_fleet_dispatch(
            {'token': fleet_dispatch.dispatch_token,
             'galaxy': dest.galaxy,
             'system': dest.system,
             'position': dest.position,
             'type': dest.type.id,
             'metal': resources.get(Resource.metal, 0),
             'crystal': resources.get(Resource.crystal, 0),
             'deuterium': resources.get(Resource.deuterium, 0),
             'prioMetal': 1,
             'prioCrystal': 2,
             'prioDeuterium': 3,
             'mission': mission.id,
             'speed': fleet_speed,
             'retreatAfterDefenderRetreat': 0,
             'union': 0,
             'holdingtime': holding_time,
             **{f'am{ship.id}': amount for ship, amount in ships.items() if amount > 0}},
            delay=delay)
        return fleet_dispatch

    def _get_overview(self,
                      planet: Union[Planet, int] = None,
                      delay: int = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'overview',
                    'cp': planet},
            delay=delay)

    def _get_research(self,
                      delay: int = None):
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'research'},
            delay=delay)

    def _get_shipyard(self,
                      planet: Union[Planet, int] = None,
                      delay: int = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'shipyard',
                    'cp': planet},
            delay=delay)

    def _get_fleet_dispatch(self,
                            planet: Union[Planet, int] = None,
                            delay: int = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'fleetdispatch',
                    'cp': planet},
            delay=delay)

    def _get_movement(self,
                      return_fleet: Union[FleetMovement, int] = None,
                      delay: int = None):
        if return_fleet is not None and isinstance(return_fleet, FleetMovement):
            return_fleet = return_fleet.id
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'movement',
                    'return': return_fleet},
            delay=delay)

    def _get_galaxy(self,
                    planet: Union[Planet, int] = None,
                    galaxy: int = None,
                    system: int = None,
                    delay: int = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(
            params={'page': 'ingame',
                    'component': 'galaxy',
                    'cp': planet,
                    'galaxy': galaxy,
                    'system': system},
            delay=delay)

    def _get_resources(self,
                       planet: Union[Planet, int] = None,
                       delay: int = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_resource(
            resource='json',
            params={'page': 'fetchResources',
                    'cp': planet,
                    'ajax': 1},
            delay=delay)

    def _get_event_list(self,
                        delay: int = None):
        return self._get_game_resource(
            resource='html',
            params={'page': 'componentOnly',
                    'component': 'eventList',
                    'ajax': 1},
            delay=delay)

    def _post_fleet_dispatch(self,
                             fleet_dispatch_data,
                             delay: int = None):
        return self._request(
            method='post',
            url=self._base_game_url,
            params={'page': 'ingame',
                    'component': 'fleetdispatch',
                    'action': 'sendFleet',
                    'ajax': 1,
                    'asJson': 1},
            data=fleet_dispatch_data,
            delay=delay)

    def _get_game_resource(self, resource, **kwargs):
        return self._request_game_resource('get', resource, **kwargs)

    def _post_game_resource(self, resource, **kwargs):
        return self._request_game_resource('post', resource, **kwargs)

    def _get_game_page(self, **kwargs):
        return self._request_game_page(method='get', **kwargs)

    def _post_game_page(self, **kwargs):
        return self._request_game_page(method='post', **kwargs)

    @keep_session()
    def _request_game_page(self, method, **kwargs):
        if not self._base_game_url:
            raise NotLoggedInError()
        response = self._request(
            method=method,
            url=self._base_game_url,
            **kwargs)
        soup = parse_html(response)
        ogame_session = soup.find('meta', {'name': 'ogame-session'})
        if not ogame_session:
            raise NotLoggedInError()
        return soup

    @keep_session()
    def _request_game_resource(self, method, resource, **kwargs):
        if not self._base_game_url:
            raise NotLoggedInError()
        response = self._request(
            method=method,
            url=self._base_game_url,
            **kwargs)
        soup = parse_html(response)
        # resource can be either a piece of html or json
        #  so a <head> tag in the html means that we landed on the login page
        if soup.find('head'):
            raise NotLoggedInError()
        if resource == 'html':
            return soup
        elif resource == 'json':
            return response.json()
        else:
            raise ValueError('unknown resource: ' + str(resource))

    @property
    def _base_game_url(self):
        if self._server_url:
            return f'https://{self._server_url}/game/index.php'

    def _get_accounts(self):
        response = self._request(
            method='get',
            url='https://lobby.ogame.gameforge.com/api/users/me/accounts',
            delay=0)
        accounts = response.json()
        if 'error' in accounts:
            raise ValueError(accounts['error'])
        return accounts

    def _get_php_session_id(self):
        response = self._request(
            method='post',
            url='https://lobby.ogame.gameforge.com/api/users',
            delay=0,
            data={'kid': '',
                  'language': self.language,
                  'autologin': 'false',
                  'credentials[email]': self.username,
                  'credentials[password]': self.password})
        for cookie in response.cookies:
            if cookie.name == 'PHPSESSID':
                return cookie.value

    def _request(self, method, url, delay=None, **kwargs):
        now = time.time()
        if delay is None:
            delay = self.delay_between_requests
        if delay:
            resume_time = self._last_request_time + delay
            if now < resume_time:
                time.sleep(resume_time - now)
        timeout = kwargs.pop('timeout', self.request_timeout)
        response = self._session.request(method, url, timeout=timeout, **kwargs)
        self._last_request_time = time.time()
        return response

    def _get_account(self):
        accounts = self._get_accounts()
        for account in accounts:
            acc_server_number = account['server']['number']
            acc_server_language = account['server']['language'].casefold()
            if self.server_number == acc_server_number and self.language == acc_server_language:
                return account

    @staticmethod
    def _parse_coords_type(figure_el):
        if 'planet' in figure_el['class']:
            return CoordsType.planet
        elif 'moon' in figure_el['class']:
            return CoordsType.moon
        elif 'tf' in figure_el['class']:
            return CoordsType.debris
        else:
            raise ValueError('Failed to parse coordinate type.')


# TODO _find_at_most_one


def _find_exactly_one(root, raise_exc=True, **kwargs):
    """ Find exactly one element. """
    descendants = _find_exactly(root, n=1, raise_exc=raise_exc, **kwargs)
    if raise_exc or descendants:
        return descendants[0]


def _find_at_least_one(root, **kwargs):
    """ Find at least one element. """
    descendants = root.find_all(**kwargs)
    if len(descendants) == 0:
        raise ParseException(f'Failed to find any descendants of:\n'
                             f'element: {root.attrs}\n'
                             f'query: {kwargs}')
    return descendants


def _find_exactly(root, n, raise_exc=True, **kwargs):
    """ Find exactly `n` elements. By default raise ParseException if exactly `n` elements were not found. """
    limit = kwargs.get('limit')
    if limit and n > limit:
        raise ValueError(f'An exact number of elements (n={n}) will never be matched '
                         f'because of the limit (limit={limit}).')
    query = dict(**kwargs)
    # exception will be thrown regardless of the number of elements,
    #  so don't match more than necessary
    query.update({'limit': n + 1})
    descendants = root.find_all(**query)
    if len(descendants) != n:
        if raise_exc:
            raise ParseException(f'Failed to find exactly (n={n}) descendant(s) of:\n'
                                 f'element: {root.attrs}\n'
                                 f'query: {kwargs}')
    else:
        return descendants
