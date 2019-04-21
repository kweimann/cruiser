import re
import xml.dom.minidom

import requests


class OGameAPI:
    def __init__(self, server_number, server_language):
        self.server_number = server_number
        self.server_language = server_language

    def get_server_data(self):
        """
        :return: server data dictionary
        """
        xml = self._get_endpoint('serverData.xml')
        timestamp = xml.firstChild.getAttribute('timestamp')
        return {
            'timestamp': int(timestamp),
            'server_data': {
                node.tagName: node.firstChild.nodeValue for node in xml.firstChild.childNodes
            }
        }

    def get_players(self):
        """
        :return: players data dictionary
        """
        xml = self._get_endpoint('players.xml')
        timestamp = xml.firstChild.getAttribute('timestamp')
        players = xml.getElementsByTagName('player')
        return {
            'timestamp': int(timestamp),
            'players': [
                {
                    'id': int(attr(player, 'id')),
                    'name': attr(player, 'name'),
                    'status': attr(player, 'status'),
                    'alliance_id': to_int(attr(player, 'alliance'))
                } for player in players
            ]
        }

    def get_universe(self):
        """
        :return: universe data dictionary
        """
        xml = self._get_endpoint('universe.xml')
        timestamp = xml.firstChild.getAttribute('timestamp')
        planets = xml.getElementsByTagName('planet')
        return {
            'timestamp': int(timestamp),
            'planets': [
                {
                    'id': int(attr(planet, 'id')),
                    'player_id': int(attr(planet, 'player')),
                    'name': attr(planet, 'name'),
                    'coordinates': extract_numbers(attr(planet, 'coords')),
                    'moon': {
                        'id': int(attr(planet.firstChild, 'id')),
                        'name': attr(planet.firstChild, 'name'),
                        'size': int(attr(planet.firstChild, 'size'))
                    } if planet.getElementsByTagName('moon') else None
                } for planet in planets
            ]
        }

    def get_highscore(self, category=1, type=0):
        """
        :param category: highscore category
            1 - player
            2 - alliance
        :param type: highscore type
            0 - points
            1 - economy
            2 - technology
            3 - military
            4 - military lost
            5 - military built
            6 - military destroyed
            7 - honor
        :return: highscore data dictionary
        """
        xml = self._get_endpoint('highscore.xml', params={'category': category, 'type': type})
        timestamp = xml.firstChild.getAttribute('timestamp')
        players = xml.getElementsByTagName('player')
        return {
            'timestamp': int(timestamp),
            'highscore': [
                {
                    'position': int(attr(player, 'position')),
                    'player_id': int(attr(player, 'id')),
                    'score': int(attr(player, 'score'))
                } for player in players
            ]
        }

    def get_alliances(self):
        """
        :return: alliance data dictionary
        """
        xml = self._get_endpoint('alliances.xml')
        timestamp = xml.firstChild.getAttribute('timestamp')
        alliances = xml.getElementsByTagName('alliance')
        return {
            'timestamp': int(timestamp),
            'alliances': [
                {
                    'id': int(attr(alliance, 'id')),
                    'name': attr(alliance, 'name'),
                    'tag': attr(alliance, 'tag'),
                    'founder_id': int(attr(alliance, 'founder')),
                    'creation_timestamp': int(attr(alliance, 'foundDate')),
                    'open': to_int(attr(alliance, 'open')),
                    'players': [
                        int(attr(player, 'id')) for player in alliance.getElementsByTagName('player')
                    ]
                } for alliance in alliances
            ]
        }

    @classmethod
    def from_universe(cls, universe, language):
        """
        :param universe: universe name
        :param language: language code
        :return: OGameAPI
        """
        server = get_server(universe, language)
        if not server:
            raise ValueError('Server not found.')
        server_number = server['number']
        server_lang = server['language']
        return cls(server_number, server_lang)

    def _get_endpoint(self, endpoint, **kwargs):
        return parse_xml(requests.get(self._api(endpoint), **kwargs))

    def _api(self, endpoint):
        return f'https://s{self.server_number}-{self.server_language}.ogame.gameforge.com/api/{endpoint}'


def get_server(universe, language):
    for server in get_servers():
        server_name = server['name']
        server_lang = server['language']
        if universe.lower() == server_name.lower() and language.lower() == server_lang.lower():
            return server


def parse_xml(response): return xml.dom.minidom.parseString(response.content)
def get_servers(): return requests.get('https://lobby-api.ogame.gameforge.com/servers').json()
def attr(node, attr_name): return node.getAttribute(attr_name) or None
def extract_numbers(string): return tuple(int(number) for number in re.findall('-?\\d+', string))
def to_int(string): return int(string) if string is not None else None
