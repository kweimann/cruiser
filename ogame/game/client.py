import functools
import logging
from typing import List, Union, Dict
from urllib.parse import urlparse

import requests

from ogame.game.const import (
    Mission,
    CoordsType,
    Resource,
    Ship,
    Technology
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
    FleetDispatch
)
from ogame.util import (
    join_digits,
    parse_html,
    extract_numbers,
    str2bool,
    tuple2timestamp,
    find_first_between,
    find_unique
)


class NotLoggedInError(Exception):
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
    def __init__(self, universe, username, password, language, request_timeout=10):
        self.universe = universe
        self.username = username
        self.password = password
        self.language = language
        self.request_timeout = request_timeout
        self._account = None
        self._server = None
        self._session = requests.session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/73.0.3683.103 '
                          'Safari/537.36'
        })
        self._server_url = None

    def login(self) -> None:
        php_session_id = self._get_php_session_id()
        if not php_session_id:
            raise ValueError('Invalid credentials.')
        login_response = self._session.get(
            'https://lobby.ogame.gameforge.com/api/users/me/loginLink',
            timeout=self.request_timeout,
            params={'id': self.account['id'],
                    'server[language]': self.server['language'],
                    'server[number]': self.server['number']})
        login_status = login_response.json()
        if 'error' in login_status:
            raise ValueError(login_status['error'])
        url = login_status['url']
        url_parsed = urlparse(url)
        self._server_url = url_parsed.netloc
        self._session.get(url, timeout=self.request_timeout)

    def get_research(self) -> Research:
        research_soup = self._get_research()
        technologies_el = research_soup.find(id='technologies')
        technologies = {}
        production = None
        for technology in Technology:
            technology_el = technologies_el.find('li', {'data-technology': technology.id}, class_='technology')
            level_el = technology_el.find('span', class_='level')
            level = int(level_el['data-value'])
            bonus = join_digits(level_el['data-bonus'])
            technologies[technology] = level + bonus
            if technology_el['data-status'] == 'active':
                if production is not None:
                    logging.warning('Multiple productions encountered.')
                    continue
                start = int(technology_el['data-start'])
                end = int(technology_el['data-end'])
                production = Production(o=technology, start=start, end=end)
        return Research(technology=technologies, production=production)

    def get_shipyard(self, planet: Union[Planet, int]) -> Shipyard:
        shipyard_soup = self._get_shipyard(planet)
        technologies_el = shipyard_soup.find(id='technologies')
        ships = {}
        production = None
        for ship in Ship:
            ship_el = technologies_el.find('li', {'data-technology': ship.id}, class_='technology')
            amount_el = ship_el.find('span', class_='amount')
            amount = int(amount_el['data-value'])
            ships[ship] = amount
            if ship_el['data-status'] == 'active':
                if production is not None:
                    logging.warning('Multiple productions encountered.')
                    continue
                target_amount_el = ship_el.find('span', class_='targetamount')
                target_amount = int(target_amount_el['data-value'])
                start = int(ship_el['data-start'])
                end = int(ship_el['data-end'])
                production = Production(o=ship, start=start, end=end, amount=target_amount - amount)
        return Shipyard(ships=ships, production=production)

    def get_resources(self, planet: Union[Planet, int]) -> Resources:
        resources = self._get_resources(planet)['resources']
        def amount(res): return int(resources[res]['amount'])
        def storage(res): return int(resources[res]['storage'])
        amounts = {Resource.metal: amount('metal'),
                   Resource.crystal: amount('crystal'),
                   Resource.deuterium: amount('deuterium'),
                   Resource.energy: amount('energy'),
                   Resource.dark_matter: amount('darkmatter')}
        storage = {Resource.metal: storage('metal'),
                   Resource.crystal: storage('crystal'),
                   Resource.deuterium: storage('deuterium')}
        return Resources(amount=amounts, storage=storage)

    def get_planets(self) -> List[Planet]:
        overview_soup = self._get_overview()
        planet_list = overview_soup.find(id='planetList')
        smallplanets = planet_list.findAll(class_='smallplanet')
        planets = []
        for planet_div in smallplanets:
            planet_id = abs(join_digits(planet_div['id']))
            planet_name = planet_div.find(class_='planet-name').text.strip()
            galaxy, system, position = extract_numbers(planet_div.find(class_='planet-koords').text)
            planet_coords = Coordinates(galaxy, system, position, CoordsType.planet)
            planet = Planet(id=planet_id,
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
                moon = Planet(id=moon_id,
                              name=moon_name,
                              coords=moon_coords)
                planets.append(moon)
        return planets

    def get_events(self) -> List[FleetEvent]:
        event_list = self._get_event_list()
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
            event = FleetEvent(id=event_id,
                               origin=origin,
                               dest=dest,
                               arrival_time=arrival_time,
                               mission=mission,
                               return_flight=return_flight,
                               player_id=player_id)
            events.append(event)
        return events

    def get_fleet_movement(self, return_fleet: Union[FleetMovement, int] = None) -> Movement:
        movement_soup = self._get_movement(return_fleet)
        movement_el = movement_soup.find(id='movement')
        timestamp = int(movement_soup.find('meta', {'name': 'ogame-timestamp'})['content'])
        if not movement_el:
            # when there is no movement the server redirects to fleet dispatch
            slot_elements = movement_soup.find(id='slots').findAll('div', recursive=False)
            used_fleet_slots, max_fleet_slots = extract_numbers(slot_elements[0].text)
            used_expedition_slots, max_expedition_slots = extract_numbers(slot_elements[1].text)
            return Movement(fleets=[],
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
                fleet = FleetMovement(id=fleet_id,
                                      origin=origin,
                                      dest=dest,
                                      departure_time=departure_time,
                                      arrival_time=arrival_time,
                                      mission=mission,
                                      return_flight=return_flight,
                                      holding=holding,
                                      holding_time=holding_time)
                fleets.append(fleet)
            return Movement(fleets=fleets,
                            used_fleet_slots=used_fleet_slots,
                            max_fleet_slots=max_fleet_slots,
                            used_expedition_slots=used_expedition_slots,
                            max_expedition_slots=max_expedition_slots,
                            timestamp=timestamp)

    def get_fleet_dispatch(self, planet: Union[Planet, int]) -> FleetDispatch:
        fleet_dispatch_soup = self._get_fleet_dispatch(planet)
        token = find_first_between(str(fleet_dispatch_soup), left='fleetSendingToken = "', right='"')
        timestamp = int(fleet_dispatch_soup.find('meta', {'name': 'ogame-timestamp'})['content'])
        slot_elements = fleet_dispatch_soup.find(id='slots').findAll('div', recursive=False)
        used_fleet_slots, max_fleet_slots = extract_numbers(slot_elements[0].text)
        used_expedition_slots, max_expedition_slots = extract_numbers(slot_elements[1].text)
        technologies_el = fleet_dispatch_soup.find(id='technologies')
        if technologies_el:
            ships = {}
            for ship in Ship:
                ship_el = technologies_el.find('li', {'data-technology': ship.id}, class_='technology')
                amount_el = ship_el.find('span', class_='amount')
                amount = int(amount_el['data-value'])
                ships[ship] = amount
        else:
            # there are no ships on this planet
            ships = {}
        return FleetDispatch(dispatch_token=token,
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
                   fleet_dispatch: FleetDispatch = None) -> FleetDispatch:
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
            fleet_dispatch = self.get_fleet_dispatch(origin)
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
             **{f'am{ship.id}': amount for ship, amount in ships.items() if amount > 0}})
        return fleet_dispatch

    @property
    def account(self):
        if self._account is None:
            accounts = self._get_accounts()
            def get_properties(account): return account['server']['number']
            account_properties = self.server['number']
            account = find_unique(account_properties, accounts, key=get_properties)
            if not account:
                raise ValueError('Account not found.')
            self._account = account
        return self._account

    @property
    def server(self):
        if self._server is None:
            servers = self._get_servers()
            def get_properties(server): return server['name'].lower(), server['language'].lower()
            server_properties = (self.universe.lower(), self.language.lower())
            server = find_unique(server_properties, servers, key=get_properties)
            if server is None:
                raise ValueError('Server not found.')
            self._server = server
        return self._server

    def _get_overview(self, planet: Union[Planet, int] = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(params={'page': 'ingame',
                                           'component': 'overview',
                                           'cp': planet})

    def _get_research(self):
        return self._get_game_page(params={'page': 'ingame',
                                           'component': 'research'})

    def _get_shipyard(self, planet: Union[Planet, int] = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(params={'page': 'ingame',
                                           'component': 'shipyard',
                                           'cp': planet})

    def _get_fleet_dispatch(self, planet: Union[Planet, int] = None):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_page(params={'page': 'ingame',
                                           'component': 'fleetdispatch',
                                           'cp': planet})

    def _get_movement(self, return_fleet: Union[FleetMovement, int] = None):
        if return_fleet is not None and isinstance(return_fleet, FleetMovement):
            return_fleet = return_fleet.id
        return self._get_game_page(params={'page': 'ingame',
                                           'component': 'movement',
                                           'return': return_fleet})

    def _get_resources(self, planet: Union[Planet, int]):
        if planet is not None and isinstance(planet, Planet):
            planet = planet.id
        return self._get_game_resource(resource='json', params={'page': 'fetchResources',
                                                                'cp': planet,
                                                                'ajax': 1})

    def _get_event_list(self):
        return self._get_game_resource(resource='html', params={'page': 'componentOnly',
                                                                'component': 'eventList',
                                                                'ajax': 1})

    def _post_fleet_dispatch(self, fleet_dispatch_data):
        return self._session.request(
            method='post',
            url=self._base_game_url,
            timeout=self.request_timeout,
            params={'page': 'ingame',
                    'component': 'fleetdispatch',
                    'action': 'sendFleet',
                    'ajax': 1,
                    'asJson': 1},
            data=fleet_dispatch_data)

    def _get_servers(self):
        response = requests.get('https://lobby.ogame.gameforge.com/api/servers',
                                timeout=self.request_timeout)
        return response.json()

    def _get_php_session_id(self):
        response = self._session.post(
            'https://lobby.ogame.gameforge.com/api/users',
            timeout=self.request_timeout,
            data={'kid': '',
                  'language': self.language,
                  'autologin': 'false',
                  'credentials[email]': self.username,
                  'credentials[password]': self.password})
        for cookie in response.cookies:
            if cookie.name == 'PHPSESSID':
                return cookie.value

    def _get_accounts(self):
        response = self._session.get('https://lobby.ogame.gameforge.com/api/users/me/accounts',
                                     timeout=self.request_timeout)
        accounts = response.json()
        if 'error' in accounts:
            raise ValueError(accounts['error'])
        return accounts

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
        response = self._session.request(method=method,
                                         url=self._base_game_url,
                                         timeout=self.request_timeout,
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
        response = self._session.request(method=method,
                                         url=self._base_game_url,
                                         timeout=self.request_timeout,
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
