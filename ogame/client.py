import functools
import logging
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ogame.api import get_server
from ogame.game.constants import MISSIONS, PLANET_TYPE
from ogame.game.ships import SHIPS
from ogame.game.technology import TECHNOLOGY


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
    def __init__(self, universe, username, password, language='en'):
        self.universe = universe
        self.username = username
        self.password = password
        self.language = language
        self.account = None
        self._session = requests.session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/73.0.3683.103 '
                          'Safari/537.36'
        })
        self._server_url = None

    def login(self):
        php_session_id = self._get_php_session_id()
        if not php_session_id:
            raise ValueError('Invalid credentials.')
        if not self.account:
            server = get_server(self.universe, self.language)
            if not server:
                raise ValueError('Server not found.')
            account = self._get_account(server)
            if not account:
                raise ValueError('Account not found.')
            account['server'] = server
            self.account = account
        account_id = self.account['id']
        language = self.account['server']['language']
        server_number = self.account['server']['number']
        login_response = self._session.get('https://lobby-api.ogame.gameforge.com/users/me/loginLink', params={
            'id': account_id,
            'server[language]': language,
            'server[number]': server_number
        })
        login_status = login_response.json()
        if 'error' in login_status:
            raise ValueError(login_status['error'])
        url = login_status['url']
        url_parsed = urlparse(url)
        self._server_url = url_parsed.netloc
        self._session.get(url)
        logging.debug('PHPSESSID=%s', php_session_id)

    def get_technology(self):
        research = self._get_research()
        technologies = {}
        for technology, technology_params in TECHNOLOGY.items():
            technology_id = technology_params['id']
            technology_el = research.find(id=f'details{technology_id}')
            desc_el = technology_el.find('span', class_='level')
            technology_level = join_digits(desc_el.text)
            technologies[technology] = technology_level
        return technologies

    def get_ships(self, planet_id):
        shipyard = self._get_shipyard(planet_id)
        ships = {}
        for ship, ship_params in SHIPS.items():
            ship_id = ship_params['id']
            ship_el = shipyard.find(id=f'details{ship_id}')
            desc_el = ship_el.find('span', class_='level')
            ship_count = join_digits(desc_el.text)
            ships[ship] = ship_count
        return ships

    def get_fleet_movement(self, return_fleet_id=None):
        movement = self._get_movement(return_fleet_id)
        slots_el = movement.find(class_='fleetSlots')
        if not slots_el:
            # when there is no movement the server redirects to fleet1
            slots_el = movement.find(id='slots').find('div')
        used_slots, max_slots = extract_numbers(slots_el.text)
        fleet_details_elements = movement.findAll(class_='fleetDetails')
        fleets = []
        for fleet_details_el in fleet_details_elements:
            fleet_id = abs(join_digits(fleet_details_el['id']))
            arrival_time = int(fleet_details_el['data-arrival-time'])
            origin_time = tuple2timestamp(extract_numbers(fleet_details_el.find(class_='origin').img['title']))
            dest_time = tuple2timestamp(extract_numbers(fleet_details_el.find(class_='destination').img['title']))
            flight_duration = abs(dest_time - origin_time)
            # note that departure time is always the time when fleet was sent
            # arrival time depends on whether it's a return flight (arrival at origin) or not (arrival at destination)
            departure_time = arrival_time - flight_duration
            mission_id = int(fleet_details_el['data-mission-type'])
            mission = next(mission for mission, id in MISSIONS.items() if id == mission_id)
            return_flight = str2bool(fleet_details_el['data-return-flight'])
            origin_coords = extract_numbers(fleet_details_el.find(class_='originCoords').text)
            origin_type_el = fleet_details_el.find(class_='originPlanet').find('figure')
            origin_type = next(class_ for class_ in origin_type_el['class'] if class_ in PLANET_TYPE)
            dest_coords = extract_numbers(fleet_details_el.find(class_='destinationCoords').text)
            dest_type_el = fleet_details_el.find(class_='destinationPlanet').find('figure')
            dest_type = next(class_ for class_ in dest_type_el['class'] if class_ in PLANET_TYPE)
            fleet = {
                'id': fleet_id,
                'arrival_time': arrival_time,
                'departure_time': departure_time,
                'return_flight': return_flight,
                'mission': mission,
                'origin_coords': origin_coords,
                'origin_type': origin_type,
                'dest_coords': dest_coords,
                'dest_type': dest_type,
            }
            fleets.append(fleet)
        return {
            'fleets': fleets,
            'slots': {
                'used': used_slots,
                'max': max_slots
            }
        }

    def send_fleet(self, planet_id, dest_coords, dest_type, ships, mission, speed=10, resources=None,
                   expedition_time=1):
        if mission in ['acs_attack', 'defend']:
            raise NotImplemented('ACS attack and defend are not supported.')
        self._get_game_page(params={'page': 'fleet1', 'cp': planet_id})
        galaxy, system, position = dest_coords
        mission_id = next(mission_id for mission_key, mission_id in MISSIONS.items() if mission_key == mission)
        ships_data = {
            'am' + str(SHIPS[ship]['id']): ship_count
            for ship, ship_count in ships.items()
            if ship_count > 0
        }
        payload = {
            'galaxy': galaxy,
            'system': system,
            'position': position,
            'type': dest_type,
            'mission': mission_id,
            'speed': speed,
            **ships_data
        }
        self._post_game_page(params={'page': 'fleet2'}, data=payload)
        payload = {
            'galaxy': galaxy,
            'system': system,
            'position': position,
            'type': dest_type,
            'mission': mission_id,
            'speed': speed,
            'union': 0,
            'acsValues': '-',
            **ships_data
        }
        fleet3 = self._post_game_page(params={'page': 'fleet3'}, data=payload)
        send_fleet_el = fleet3.find(id='sendfleet')
        token_el = send_fleet_el.find('input', {'name': 'token'})
        if not token_el:
            return {'error': 'bad flight configuration'}
        token = token_el['value']
        resources = resources or {}
        payload = {
            'token': token,
            'galaxy': galaxy,
            'system': system,
            'position': position,
            'type': dest_type,
            'mission': mission_id,
            'speed': speed,
            'holdingtime': 1,
            'expeditiontime': expedition_time,
            'holdingOrExpTime': 0,
            'prioMetal': 3,
            'prioCrystal': 2,
            'prioDeuterium': 1,
            'union2': 0,
            'acsValues': '-',
            'metal': resources.get('metal', 0),
            'crystal': resources.get('crystal', 0),
            'deuterium': resources.get('deuterium', 0),
            **ships_data
        }
        min_departure_time = int(time.time())
        self._post_game_page(params={'page': 'movement', **payload}, data={'token': token})
        max_departure_time = time.time()
        fleets = self.get_fleet_movement()['fleets']
        # It is assumed that the client sends all requests sequentially. If that is the case then
        # two flights may not share a single departure time. Moreover there are no overlapping
        # intervals [min_departure_time, max_departure_time] between any two flights. Consequently,
        # if a fleet was successfully sent then the flight should be uniquely matched using the departure time.

        # However, the departure time is always rounded to the second. As result,
        # it is advised to keep a delay between sending two fleets so that
        # their departure times don't overlap due to rounding
        matching_fleets = []
        for fleet in fleets:
            if min_departure_time <= fleet['departure_time'] <= max_departure_time \
                    and not fleet['return_flight'] \
                    and fleet['mission'] == mission \
                    and fleet['dest_coords'] == dest_coords \
                    and fleet['dest_type'] == dest_type:
                matching_fleets.append(fleet)
        if len(matching_fleets) > 1:
            raise ValueError('More than 1 fleet was matched.')
        elif len(matching_fleets):
            return matching_fleets[0]
        else:
            return {'error': 'fleet not sent'}

    def return_fleet(self, fleet_id):
        fleets = self.get_fleet_movement(fleet_id)['fleets']
        for fleet in fleets:
            if fleet_id == fleet['id']:
                return fleet['return_flight']
        return False

    def get_events(self):
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
            mission_id = int(event_el['data-mission-type'])
            mission = next(mission for mission, id in MISSIONS.items() if id == mission_id)
            origin_coords = extract_numbers(event_el.find(class_='coordsOrigin').text)
            origin_type_el = event_el.find(class_='originFleet').find('figure')
            origin_type = next(class_ for class_ in origin_type_el['class'] if class_ in PLANET_TYPE)
            dest_coords = extract_numbers(event_el.find(class_='destCoords').text)
            dest_type_el = event_el.find(class_='destFleet').find('figure')
            dest_type = next(class_ for class_ in dest_type_el['class'] if class_ in PLANET_TYPE)
            player_id_el = event_el.find('a', class_='sendMail')
            player_id = int(player_id_el['data-playerid']) if player_id_el else None
            event = {
                'id': event_id,
                'arrival_time': arrival_time,
                'return_flight': return_flight,
                'mission': mission,
                'origin_coords': origin_coords,
                'origin_type': origin_type,
                'dest_coords': dest_coords,
                'dest_type': dest_type,
                'player_id': player_id
            }
            events.append(event)
        return events

    def get_resources(self, planet_id):
        resources = self._get_resources(planet_id)
        metal = resources['metal']['resources']
        crystal = resources['crystal']['resources']
        deuterium = resources['deuterium']['resources']
        energy = resources['energy']['resources']
        darkmatter = resources['darkmatter']['resources']
        return {
            'metal': {
                'amount': metal['actual'],
                'max': metal['max'],
                'production': metal['production']
            },
            'crystal': {
                'amount': crystal['actual'],
                'max': crystal['max'],
                'production': crystal['production']
            },
            'deuterium': {
                'amount': deuterium['actual'],
                'max': deuterium['max'],
                'production': deuterium['production']
            },
            'energy': {
                'amount': energy['actual']
            },
            'darkmatter': {
                'amount': darkmatter['actual']
            }
        }

    def get_planets(self):
        overview = self._get_overview()
        planet_list = overview.find(id='planetList')
        smallplanets = planet_list.findAll(class_='smallplanet')
        planets = []
        for planet_div in smallplanets:
            planet_id = abs(join_digits(planet_div['id']))
            planet_name = planet_div.find(class_='planet-name').text.strip()
            planet_coordinates = extract_numbers(planet_div.find(class_='planet-koords').text)
            planet = {
                'id': planet_id,
                'name': planet_name,
                'coordinates': planet_coordinates,
                'type': 'planet'
            }
            planets.append(planet)
            moon_el = planet_div.find(class_='moonlink')
            if moon_el:
                # TODO
                moon = {
                    'id': None,
                    'name': None,
                    'coordinates': planet_coordinates,
                    'type': 'moon'
                }
                planets.append(moon)
        return planets

    def _get_overview(self, planet_id=None):
        return self._get_game_page(params={'page': 'overview', 'cp': planet_id})

    def _get_research(self):
        return self._get_game_page(params={'page': 'research'})

    def _get_shipyard(self, planet_id=None):
        return self._get_game_page(params={'page': 'shipyard', 'cp': planet_id})

    def _get_movement(self, return_fleet_id=None):
        return self._get_game_page(params={'page': 'movement', 'return': return_fleet_id})

    def _get_event_box(self):
        return self._get_game_resource(resource='json', params={'page': 'fetchEventbox'})

    def _get_resources(self, planet_id):
        return self._get_game_resource(resource='json', params={'page': 'fetchResources', 'cp': planet_id})

    def _get_event_list(self):
        return self._get_game_resource(resource='html', params={'page': 'eventList'})

    def _get_php_session_id(self):
        response = self._session.post(url='https://lobby-api.ogame.gameforge.com/users', data={
            'kid': '',
            'language': self.language,
            'autologin': 'false',
            'credentials[email]': self.username,
            'credentials[password]': self.password
        })
        for cookie in response.cookies:
            if cookie.name == 'PHPSESSID':
                return cookie.value

    def _get_account(self, server):
        response = self._session.get('https://lobby-api.ogame.gameforge.com/users/me/accounts')
        accounts = response.json()
        if 'error' in accounts:
            raise ValueError(accounts['error'])
        for account in accounts:
            account_server = account['server']
            if account_server['number'] == server['number']:
                return account

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
        response = self._session.request(method=method, url=self._base_game_url, **kwargs)
        soup = parse_html(response)
        ogame_session = soup.find('meta', {'name': 'ogame-session'})
        if not ogame_session:
            raise NotLoggedInError()
        return soup

    @keep_session()
    def _request_game_resource(self, method, resource, **kwargs):
        if not self._base_game_url:
            raise NotLoggedInError()
        response = self._session.request(method=method, url=self._base_game_url, **kwargs)
        soup = parse_html(response)
        # resource can be either a piece of html or json
        # so a <head> tag in the html means that we landed on the login page
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


def tuple2timestamp(date_tuple):
    return int(datetime(**dict(zip(['day', 'month', 'year', 'hour', 'minute', 'second'], date_tuple))).timestamp())


def join_digits(string):
    number = re.sub('[^-?\\d+]', '', string)
    return int(number) if number else None


def parse_html(response): return BeautifulSoup(response.content, 'html.parser')
def extract_numbers(string): return tuple(int(number) for number in re.findall('-?\\d+', string))
def str2bool(string): return string in ['true', 'True', '1', 'yes']
