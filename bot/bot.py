import logging
import sys
import time
import random

from bot import eventloop
from bot.protocol import *
from ogame.client import OGame
from ogame.api import (
    OGameAPI,
    get_server
)
from ogame.game.calc import (
    flight_duration,
    distance,
    fuel_consumption,
    cargo_capacity,
)


class OGameBot:
    def __init__(self, client: OGame, scheduler: eventloop.Scheduler):
        self.client = client
        self.scheduler = scheduler
        self._exc_retry_delays = [5, 10, 15, 30, 60]  # seconds
        self._periodic_wakeup_min = 5 * 60  # seconds
        self._periodic_wakeup_max = 7 * 60  # seconds
        self._periodic_wakeup_id = None
        self._server_data = None
        self._listeners = []
        self._seen_events = {}
        self._exc_count = 0

    def start(self):
        self._periodic_wakeup_id = self.scheduler.push(delay=0,
                                                       priority=0,
                                                       data=FetchEvents(),
                                                       period=lambda: random.uniform(self._periodic_wakeup_min,
                                                                                     self._periodic_wakeup_max))

    def handle_event(self, event):
        logging.info('Received event: %s', event)
        try:
            if isinstance(event, FetchEvents):
                self.fetch_events()
            self._exc_count = 0
        except:
            # keep retrying event handling in case of an exception
            retry_delay_index = min(self._exc_count, len(self._exc_retry_delays) - 1)
            retry_delay = self._exc_retry_delays[retry_delay_index]
            self.scheduler.push(retry_delay, 0, event)
            self._exc_count += 1
            logging.exception("Exception thrown %d times during event handling. Retrying in %d seconds",
                              self._exc_count, retry_delay)
            self._notify_exception()

    def fetch_events(self):
        now = time.time()
        planets = self.client.get_planets()
        events = self.client.get_events()
        seen_event_ids = self._filter_seen_event_ids(events)
        movement = None
        technology = None
        free_fleet_slots = 0
        logs = []
        for planet in planets:
            incoming_events = filter_incoming_events(planet, events)
            hostile_events = filter_mission(incoming_events, ['attack', 'acs_attack'])
            if not hostile_events:
                # planet is not under attack
                continue
            earliest_hostile_event = get_earliest_event(hostile_events)
            earliest_hostile_arrival = earliest_hostile_event['arrival_time']
            logging.info('Hostile fleet arrives at %s %s on %s',
                         planet['name'], planet['coordinates'], time.ctime(earliest_hostile_arrival))
            # if there is an attack later than 3 minutes from now
            if earliest_hostile_arrival > now + 3 * 60:
                hostile_event_id = earliest_hostile_event['id']
                # schedule future escape event only if this hostile event has not been seen before
                # to avoid repeating the same escape event
                if hostile_event_id not in seen_event_ids:
                    escape_time = earliest_hostile_arrival - random.randint(90, 150)
                    self.scheduler.pushabs(escape_time, 0, FetchEvents())
                    # save all information regarding the scheduled escape in the scheduled_escape_log
                    scheduled_escape_log = {
                        'log_name': 'scheduled_escape',
                        'origin': planet,
                        'hostile_arrival': earliest_hostile_arrival,
                        'escape_time': escape_time
                    }
                    logging.info('Scheduled escape from %s %s at %s',
                                 planet['name'], planet['coordinates'], time.ctime(escape_time))
                    logs.append(scheduled_escape_log)
            # else attempt to defend planets with less than 3 minutes left until an attack
            else:
                # get own fleet movement in case a fleet needs to be returned
                if not movement:
                    movement = self.client.get_fleet_movement()
                    max_fleet_slots = movement['slots']['max']
                    used_fleet_slots = movement['slots']['used']
                    free_fleet_slots = max_fleet_slots - used_fleet_slots
                incoming_fleets = filter_incoming_events(planet, movement['fleets'])
                deployment_fleets = filter_mission(incoming_fleets, 'deployment')
                for fleet in deployment_fleets:
                    fleet_arrival = fleet['arrival_time']
                    return_flight = fleet['return_flight']
                    # return deployment fleets to a planet under attack if the fleet arrives
                    # before next wake up. This is to make sure that opponent delaying the attack
                    # will not be able to snipe incoming fleet
                    if not return_flight and fleet_arrival <= now + self._periodic_wakeup_max + 2 * 60:
                        fleet_id = fleet['id']
                        fleet_returned = self.client.return_fleet(fleet_id)
                        # save all information regarding the return in the return_log
                        return_log = {
                            'log_name': 'return_flight',
                            'hostile_arrival': earliest_hostile_arrival,
                            'fleet': fleet
                        }
                        if not fleet_returned:
                            return_log.update({'error': 'failed to return fleet'})
                        logs.append(return_log)
                planet_id = planet['id']
                ships = self.client.get_ships(planet_id)
                # save all information regarding the escape in the escape_log
                escape_log = {
                    'log_name': 'escape_attack',
                    'origin': planet,
                    'ships': ships,
                    'hostile_arrival': earliest_hostile_arrival,
                    'incoming_deployment': deployment_fleets or None
                }
                # make sure there is any fleet on the planet
                if ships_exist(ships):
                    # make sure there are free fleet slots
                    if free_fleet_slots > 0:
                        if not technology:
                            technology = self.client.get_technology()
                        server_data = self._get_server_data()
                        fleet_speed_modifier = float(server_data.get('speedFleet', 1.))
                        fuel_consumption_modifier = float(server_data.get('globalDeuteriumSaveFactor', 1.))
                        escape_flights = get_escape_flights(origin_planet=planet,
                                                            destinations=planets,
                                                            ships=ships,
                                                            technology=technology,
                                                            fleet_speed_modifier=fleet_speed_modifier,
                                                            fuel_consumption_modifier=fuel_consumption_modifier)
                        # if there exist escape flights then pick the cheapest one
                        cheapest_escape_flight = get_cheapest_flight(escape_flights)
                        if cheapest_escape_flight:
                            escape_log.update({
                                'escape_flight': cheapest_escape_flight,
                            })
                            resources = self.client.get_resources(planet_id)
                            deuterium = resources['deuterium']['amount']
                            fuel_consumption_ = cheapest_escape_flight['fuel_consumption']
                            # make sure there is enough fuel to make the flight
                            if deuterium >= fuel_consumption_:
                                dest_coords = cheapest_escape_flight['destination']['coordinates']
                                dest_type = cheapest_escape_flight['destination']['type']
                                speed = cheapest_escape_flight['speed']
                                # calculate resources that can be saved, adjust for used fuel
                                resources['deuterium']['amount'] -= fuel_consumption_
                                cargo = get_cargo(resources=resources,
                                                  ships=ships,
                                                  technology=technology)
                                # save fleet
                                flight_data = self.client.send_fleet(planet_id=planet_id,
                                                                     dest_coords=dest_coords,
                                                                     dest_type=dest_type,
                                                                     ships=ships,
                                                                     mission='deployment',
                                                                     speed=speed,
                                                                     resources=cargo)
                                if 'error' not in flight_data:
                                    escape_log.update({
                                        'flight_data': flight_data,
                                        'resources': cargo
                                    })
                                    # a fleet slot has just been used up
                                    free_fleet_slots -= 1
                                else:
                                    escape_log.update({'error': flight_data['error']})
                            else:
                                escape_log.update({'error': 'not enough fuel'})
                        else:
                            escape_log.update({'error': 'no escape route'})
                    else:
                        escape_log.update({'error': 'no free fleet slots'})
                else:
                    escape_log.update({'error': 'no ships'})
                logging.info('Escape from %s %s: %s', planet['name'], planet['coordinates'], escape_log)
                logs.append(escape_log)
        # update seen events: this removes finished events, updates changed events and inserts new ones
        self._seen_events = {event['id']: event for event in events}
        if logs:
            notification = {
                'name': 'fetch-events',
                'data': logs
            }
            self._notify(notification)

    def add_listener(self, listener):
        self._listeners.append(listener)

    def remove_listener(self, listener):
        self._listeners.remove(listener)

    @property
    def started(self):
        return self._periodic_wakeup_id is not None

    def _filter_seen_event_ids(self, events):
        """
        :param events: list of events
        :return: list of ids of events that were already seen and have not changed since
        """
        seen_event_ids = []
        for event in events:
            event_id = event['id']
            if event_id in self._seen_events:
                arrival_time = event['arrival_time']
                seen_arrival_time = self._seen_events[event_id]['arrival_time']
                # additional arrival time check is necessary because flights may be delayed
                # i.e. the arrival time changes so the event has to be handled again
                if arrival_time == seen_arrival_time:
                    seen_event_ids.append(event_id)
        return seen_event_ids

    def _get_server_data(self):
        """
        Uses OGameAPI to get server data with all universe parameters
        :return: server data dictionary
        """
        if self._server_data is None:
            if not self.client.account:
                server = get_server(self.client.universe, self.client.language)
                if not server:
                    raise ValueError('Server not found.')
            else:
                server = self.client.account['server']
            server_number = server['number']
            server_lang = server['language']
            api_client = OGameAPI(server_number, server_lang)
            self._server_data = api_client.get_server_data()['server_data']
        return self._server_data

    def _notify(self, notification):
        for listener in self._listeners:
            listener.notify(notification)

    def _notify_exception(self):
        exc_type, exc_value, tb = sys.exc_info()
        for listener in self._listeners:
            listener.notify_exception(exc_type, exc_value, tb)


def get_escape_flights(origin_planet, destinations, ships, technology,
                       fleet_speed_modifier=1., fuel_consumption_modifier=1.):
    """
    :param origin_planet: origin planet
    :param destinations: list of planets (accepts planets not controlled by the player)
    :param ships: ships on origin planet
    :param technology: technology
    :param fleet_speed_modifier: universe fleet speed
    :param fuel_consumption_modifier: universe deuterium save factor
    :return: list of escape flights
    """
    escape_flights = []
    for destination in destinations:
        distance_ = distance_planets(origin_planet, destination)
        if distance_ > 0:  # target_planet != destination
            for speed in range(10):
                speed_percentage = 10 * (speed + 1)
                flight_duration_ = flight_duration(distance=distance_,
                                                   ships=ships,
                                                   speed_percentage=speed_percentage,
                                                   universe_fleet_speed_modifier=fleet_speed_modifier,
                                                   technology=technology)
                fuel_consumption_ = fuel_consumption(distance=distance_,
                                                     ships=ships,
                                                     speed_percentage=speed_percentage,
                                                     technology=technology,
                                                     universe_fleet_speed_modifier=fleet_speed_modifier,
                                                     universe_fuel_consumption_modifier=fuel_consumption_modifier)
                escape_flight = {
                    'destination': destination,
                    'duration': flight_duration_,
                    'speed': speed + 1,
                    'fuel_consumption': fuel_consumption_,
                }
                escape_flights.append(escape_flight)
    return escape_flights


def get_cargo(resources, ships, technology):
    """
    Get resources that can be loaded on the ships.
    Priority descending: deuterium, crystal, metal.
    :param resources: resources
    :param ships: ships
    :param technology: technology
    :return: dictionary { resource: amount }
    """
    loaded_resources = {}
    free_cargo_capacity = cargo_capacity(ships, technology)
    for resource_key in ['deuterium', 'crystal', 'metal']:
        if free_cargo_capacity <= 0:
            break
        amount = resources[resource_key]['amount']
        loaded_amount = min(amount, free_cargo_capacity)
        loaded_resources[resource_key] = loaded_amount
        free_cargo_capacity -= loaded_amount
    return loaded_resources


def filter_incoming_events(planet, events):
    """
    :param planet: planet
    :param events: list of events
    :return: list of events whose destination is given planet
    """
    return [event for event in events
            if event['dest_coords'] == planet['coordinates']
            and event['dest_type'] == planet['type']]


def filter_mission(events, missions):
    """
    :param events: list of events
    :param missions: single mission or a list of missions
    :return: list of events with selected mission
    """
    if not isinstance(missions, list):
        missions = [missions]
    return [event for event in events if event['mission'] in missions]


def distance_planets(p1, p2): return 0 if equal_coords(p1, p2) else distance(p1['coordinates'], p2['coordinates'])
def equal_coords(p1, p2): return p1['coordinates'] == p2['coordinates'] and p1['type'] == p2['type']
def get_earliest_event(events): return min(events, key=lambda event: event['arrival_time']) if events else None
def get_cheapest_flight(flights): return min(flights, key=lambda flight: flight['fuel_consumption']) if flights else None
def ships_exist(ships): return len(ships) and any(ship_count for ship_count in ships.values())
