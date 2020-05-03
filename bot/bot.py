import logging
import random
import sys
import time
import uuid
from typing import List, Union, Dict, Tuple

from bot.eventloop import Scheduler
from bot.protocol import FetchEvents
from ogame import (
    OGame,
    OGameAPI,
    Engine
)
from ogame.game.const import (
    Mission,
    Resource,
    Ship,
    Technology
)
from ogame.game.model import (
    Coordinates,
    Planet,
    FleetEvent,
    CoordsType,
    FleetMovement,
    Movement
)


class OGameBot:
    def __init__(self, client: OGame, scheduler: Scheduler, **kwargs):
        self.client = client
        self.scheduler = scheduler
        self._listeners = []
        self._engine = None
        self._periodic_wakeup_id = None
        self._earliest_seen_hostile_events = {}  # planet.id -> (planet, earliest_hostile_event)
        self._periodic_wakeup_min = kwargs.get('periodic_wakeup_min', 10 * 60)  # 10 minutes
        self._periodic_wakeup_max = kwargs.get('periodic_wakeup_max', 15 * 60)  # 15 minutes
        self._min_time_before_attack_to_act = kwargs.get('min_time_before_attack_to_act', 2 * 60)  # 2 minutes
        self._max_time_before_attack_to_act = kwargs.get('max_time_before_attack_to_act', 3 * 60)  # 3 minutes
        self._retry_event_id = uuid.uuid4().hex
        self._exc_retry_delays = [5, 10, 15, 30, 60]  # seconds
        self._exc_count = 0

    def start(self):
        if self._engine is None:
            self._engine = Engine(self._get_server_data())
        if self._periodic_wakeup_id is None:
            self._periodic_wakeup_id = self.scheduler.push(delay=0,
                                                           priority=0,
                                                           data=FetchEvents(),
                                                           period=lambda: random.uniform(self._periodic_wakeup_min,
                                                                                         self._periodic_wakeup_max))

    def stop(self):
        self.scheduler.cancel(self._periodic_wakeup_id)
        self._periodic_wakeup_id = None

    def add_listener(self, listener):
        self._listeners.append(listener)

    def remove_listener(self, listener):
        self._listeners.remove(listener)

    @property
    def started(self):
        return self._periodic_wakeup_id is not None

    def handle_event(self, event):
        if not self.started:
            raise ValueError('OGameBot has not been started yet.')
        if isinstance(event, FetchEvents):
            self._handle_fetch_events(event)

    @property
    def _retrying_after_exception(self):
        return self._exc_count > 0

    def _handle_fetch_events(self, event: FetchEvents):
        if self._retrying_after_exception:
            # Ignore any incoming events during retrying. Once the retry event is successful
            #  all the ignored events will be handled simultaneously during handling of that retry event.
            if event.id != self._retry_event_id:
                return
        try:
            self._fetch_events()
            self._exc_count = 0
        except Exception:
            retry_delay_index = min(self._exc_count, len(self._exc_retry_delays) - 1)
            retry_delay = self._exc_retry_delays[retry_delay_index]
            retry_event = FetchEvents(self._retry_event_id)
            self.scheduler.push(retry_delay, 0, retry_event)
            self._exc_count += 1
            logging.exception(f'Exception thrown {self._exc_count} times during event handling. '
                              f'Retrying in {retry_delay} seconds.')
            self._notify_listeners_exception()
            raise

    def _fetch_events(self):
        logs = []
        movement = None
        technology = None
        exception_raised = False
        planets = self.client.get_planets()
        events = self.client.get_events()
        earliest_hostile_events = get_earliest_hostile_events(events, planets)
        # log fleet events
        if events:
            events_string = '\n'.join(map(str, events))
            logging.debug(f'Fleet events:\n{events_string}')
            if not earliest_hostile_events:
                logging.info('No hostile fleets on sight. Your planets are safe.')
        else:
            logging.info('No fleet movement has been detected.')
        # only check planets currently under attack
        for planet, earliest_hostile_event in earliest_hostile_events.values():
            try:
                earliest_hostile_arrival = earliest_hostile_event.arrival_time
                logging.info(f'Hostile fleet arrives at {planet} on {time.ctime(earliest_hostile_arrival)}')
                # if there is an attack later than the minimum time difference between now and the attack
                if earliest_hostile_arrival > now() + self._max_time_before_attack_to_act:
                    _, earliest_seen_hostile_event = self._earliest_seen_hostile_events.get(planet.id, (None, None))
                    # schedule future escape event only if this hostile event has not been seen before
                    #  to avoid repeating the same escape event
                    if earliest_seen_hostile_event is None \
                            or earliest_hostile_arrival == earliest_seen_hostile_event.arrival_time:
                        time_before_attack_to_act = random.randint(self._min_time_before_attack_to_act,
                                                                   self._max_time_before_attack_to_act)
                        escape_time = earliest_hostile_arrival - time_before_attack_to_act
                        self.scheduler.pushabs(escape_time, 0, FetchEvents())
                        # save all information regarding the scheduled escape in the scheduled_escape_log
                        scheduled_escape_log = {
                            'log_name': 'scheduled_escape',
                            'origin': planet,
                            'hostile_arrival': earliest_hostile_arrival,
                            'escape_time': escape_time
                        }
                        logging.info(f'Scheduled escape from {planet} on {time.ctime(escape_time)}')
                        logs.append(scheduled_escape_log)
                # else attempt to defend planets with less than than the specified minimum time left until an attack
                else:
                    # Returning fleets to a planet under attack are not considered during fleet saving
                    #  i.e. bot doesn't wait for returning fleets. As long as returning fleet is not being
                    #  deliberately sniped by an opponent, the chances of fleet returning at a time between the
                    #  attack and fleet save are quite low.
                    # ---
                    # get own fleet movement in case a fleet needs to be returned
                    if not movement:
                        movement = self.client.get_fleet_movement()
                    incoming_fleets = filter_incoming(planet, movement.fleets)
                    deployment_fleets = filter_by_mission(incoming_fleets, Mission.deployment)
                    for fleet in deployment_fleets:
                        # Return deployment fleets if the destination is under attack and the fleet arrives
                        #  before the next wake up (+ maximum time the bot has to act in case of an attack).
                        #  This ensures that if the opponent delays the attack,
                        #  she will not be able to snipe the incoming fleet.
                        next_wakeup = now() + self._periodic_wakeup_max + self._max_time_before_attack_to_act
                        if not fleet.return_flight and fleet.arrival_time <= next_wakeup:
                            movement = self.client.get_fleet_movement(return_fleet=fleet)
                            # save all information regarding the return in the return_log
                            return_log = {
                                'log_name': 'return_flight',
                                'hostile_arrival': earliest_hostile_arrival,
                                'fleet': fleet
                            }
                            # Make sure that fleet was sent. Note that it is not possible to distinguish
                            #  between not returned fleet and not found fleet.
                            if fleet_returned(fleet, movement):
                                logging.info(f'Recalling fleet {fleet.id} was successful.')
                            else:
                                return_log.update({'error': 'Failed to return fleet.'})
                                logging.warning(f'Recalling fleet {fleet.id} failed: {return_log["error"]}')
                            logs.append(return_log)
                    ships = self.client.get_shipyard(planet).ships
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
                        if movement.free_slots > 0:
                            if not technology:
                                technology = self.client.get_research().technology
                            escape_flights = get_escape_flights(engine=self._engine,
                                                                origin=planet,
                                                                destinations=planets,
                                                                ships=ships,
                                                                technology=technology)
                            # Why destinations under attack where the hostile fleets arrive
                            #  before our deployment are not discarded? First, that would not work
                            #  flawlessly e.g. what if all destinations meet the requirements to be discarded.
                            #  Second, if need be, escaping fleet might be returned later. In this case,
                            #  a smart opponent who knows how this bot works will force a return and attempt to snipe
                            #  the returning fleet. This is possible but chances of this happening are very slim,
                            #  especially, since this bot is designed to save the fleet if the user fails to do so.
                            #  In that context, it's the user's responsibility to react to a hostile event first.
                            #  Furthermore, taking these additional precautions may cause a significantly higher
                            #  fuel consumption.
                            # ---
                            # if there exist escape flights then pick the cheapest one
                            cheapest_escape_flight = get_cheapest_flight(escape_flights)
                            if cheapest_escape_flight:
                                escape_log.update({
                                    'escape_flight': cheapest_escape_flight,
                                })
                                resources = self.client.get_resources(planet).amount
                                deuterium = resources[Resource.deuterium]
                                fuel_consumption = cheapest_escape_flight['fuel_consumption']
                                # make sure there is enough fuel to make the flight
                                if deuterium >= fuel_consumption:
                                    destination = cheapest_escape_flight['destination']
                                    fleet_speed = cheapest_escape_flight['fleet_speed']
                                    # calculate resources that can be saved, adjust for used fuel
                                    resources[Resource.deuterium] -= fuel_consumption
                                    cargo = get_cargo(engine=self._engine,
                                                      resources=resources,
                                                      ships=ships,
                                                      technology=technology)
                                    # save fleet
                                    flight_data = self.client.dispatch_fleet(origin=planet,
                                                                             dest=destination,
                                                                             ships=ships,
                                                                             mission=Mission.deployment,
                                                                             fleet_speed=fleet_speed,
                                                                             resources=cargo)
                                    # make sure fleet was sent
                                    movement = self.client.get_fleet_movement()
                                    fleets = get_matching_fleets(flight_data, movement)
                                    if len(fleets) == 1:
                                        escape_log.update({'fleet': fleets[0]})
                                    elif len(fleets) > 1:
                                        escape_log.update({'error': 'Multiple fleets matched.'})
                                    else:
                                        escape_log.update({'error': 'Failed to find the fleet. '
                                                                    'The fleet may have not been dispatched at all.'})
                                else:
                                    escape_log.update({'error': 'Not enough fuel.'})
                            else:
                                escape_log.update({'error': 'No escape route.'})
                        else:
                            escape_log.update({'error': 'No free fleet slots.'})
                    else:
                        escape_log.update({'error': 'No ships.'})
                    if 'error' in escape_log:
                        logging.warning(f'Escape from {planet} failed: {escape_log["error"]}')
                    else:
                        logging.info(f'Escape from {planet} was successful')
                    logs.append(escape_log)
            except Exception as e:
                logging.exception(f"Exception occurred while handling hostile events on {planet}")
                self._notify_listeners_exception(e)
                exception_raised = True
        # update the earliest seen hostile events
        self._earliest_seen_hostile_events = earliest_hostile_events
        # notify listeners about actions taken
        self._notify_listeners(logs)
        if exception_raised:
            raise ValueError('Exceptions occurred during event handling.')

    def _notify_listeners(self, logs):
        """
        Notify listeners about actions taken.
        :param logs: list of logs or single log object
        """
        if not isinstance(logs, list):
            logs = [logs]
        for log in logs:
            for listener in self._listeners:
                listener.notify(log)

    def _notify_listeners_exception(self, e=None):
        """
        Notify listeners about an exception. By default the last thrown exception is reported.
        """
        if e is None:
            e = sys.exc_info()
        elif isinstance(e, Exception):
            exc_type = type(e)
            exc_tb = e.__traceback__
            e = (exc_type, e, exc_tb)
        for listener in self._listeners:
            listener.notify_exception(e)

    def _get_server_data(self):
        server_number = self.client.server['number']
        server_lang = self.client.server['language']
        api_client = OGameAPI(server_number, server_lang)
        server_data = api_client.get_server_data()['server_data']
        return server_data


def get_escape_flights(engine: Engine,
                       origin: Union[Planet, Coordinates],
                       destinations: List[Union[Planet, Coordinates]],
                       ships: Dict[Ship, int],
                       technology: Dict[Technology, int] = None):
    """
    :param engine: game engine
    :param origin: origin planet
    :param destinations: list of planets (accepts planets not controlled by the player)
    :param ships: dictionary describing the size of the fleet on the planet
    :param technology: dictionary describing the current technology levels
    :return: list of escape flights:
    {
        destination: Coordinates,
        duration: int,
        fleet_speed: int,
        fuel_consumption: int,
    }
    """
    if isinstance(origin, Planet):
        origin = origin.coords
    escape_flights = []
    for destination in destinations:
        if isinstance(destination, Planet):
            destination = destination.coords
        if origin != destination:
            distance = engine.distance(origin, destination)
            for fleet_speed in range(10):
                speed_percentage = 10 * (fleet_speed + 1)
                flight_duration = engine.flight_duration(distance=distance,
                                                         ships=ships,
                                                         fleet_speed=speed_percentage,
                                                         technology=technology)
                fuel_consumption = engine.fuel_consumption(distance=distance,
                                                           ships=ships,
                                                           flight_duration=flight_duration,
                                                           technology=technology)
                escape_flight = {
                    'destination': destination,
                    'duration': flight_duration,
                    'fleet_speed': fleet_speed + 1,
                    'fuel_consumption': fuel_consumption,
                }
                escape_flights.append(escape_flight)
    return escape_flights


def get_cargo(engine: Engine,
              resources: Dict[Resource, int],
              ships: Dict[Ship, int],
              technology: Dict[Technology, int] = None) -> Dict[Resource, int]:
    """
    Get resources that can be loaded on the ships.
    Priority descending: deuterium, crystal, metal.
    :param engine: game engine
    :param resources: dictionary describing the available resources
    :param ships: dictionary describing the size of the fleet
    :param technology: dictionary describing the current technology levels
    :return: dictionary describing the cargo
    """
    loaded_resources = {}
    free_cargo_capacity = engine.cargo_capacity(ships, technology)
    for resource in [Resource.deuterium, Resource.crystal, Resource.metal]:
        if free_cargo_capacity <= 0:
            break
        if resource not in resources:
            logging.warning(f'Missing {resource} in resources.')
        amount = resources.get(resource, 0)
        loaded_amount = min(amount, free_cargo_capacity)
        loaded_resources[resource] = loaded_amount
        free_cargo_capacity -= loaded_amount
    return loaded_resources


def get_earliest_hostile_events(events: List[FleetEvent],
                                planets: List[Planet]) -> Dict[int, Tuple[Planet, FleetEvent]]:
    """ Get earliest hostile event for each planet. """
    earliest_hostile_events = {}
    for planet in planets:
        incoming_events = filter_incoming(planet, events)
        hostile_events = filter_by_mission(incoming_events, [Mission.attack, Mission.acs_attack])
        earliest_hostile_event = get_earliest_event(hostile_events)
        if earliest_hostile_event is not None:
            earliest_hostile_events[planet.id] = (planet, earliest_hostile_event)
    return earliest_hostile_events


def get_matching_fleets(flight_data,
                        movement: Movement) -> List[FleetMovement]:
    """ Get fleets matching the flight data. """
    def matches_fleet_movement(fleet):
        return flight_data['dest'] == fleet.dest \
               and flight_data['mission'] == fleet.mission \
               and flight_data['timestamp'] <= fleet.departure_time <= movement.timestamp
    return list(filter(matches_fleet_movement, movement.fleets))


def filter_incoming(dest: Union[Coordinates, Planet],
                    events: List[Union[FleetEvent, FleetMovement]]) -> List[Union[FleetEvent, FleetMovement]]:
    """ Get fleets heading towards planet. """
    if isinstance(dest, Planet):
        dest = dest.coords
    return [e for e in events if dest == e.dest]


def filter_by_mission(events: List[Union[FleetEvent, FleetMovement]],
                      missions: Union[Mission, List[Mission]]) -> List[Union[FleetEvent, FleetMovement]]:
    """ Get fleets with one of the missions. """
    if isinstance(missions, Mission):
        missions = [missions]
    return [e for e in events if e.mission in missions]


def get_earliest_event(events: List[FleetEvent]) -> FleetEvent:
    """ Get the fleet that is arriving first. """
    return min(events, key=lambda e: e.arrival_time) if events else None


def get_cheapest_flight(flights):
    """ Get flight which lowest fuel consumption, prefer moons over planets. """
    def priority(flight): return - flight['fuel_consumption'], flight['destination'].type == CoordsType.moon
    return max(flights, key=priority) if flights else None


def fleet_returned(fleet: Union[FleetMovement, int],
                   movement: Movement) -> bool:
    """ Check whether fleet was returned.
    Note that it is not possible to distinguish between not returned fleet and not found fleet. """
    if isinstance(fleet, FleetMovement):
        fleet = fleet.id
    for fleet_movement in movement.fleets:
        if fleet_movement.id == fleet:
            return fleet_movement.return_flight
    return False


def ships_exist(ships: Dict[Ship, int]) -> bool:
    """ Check whether there are any ships. """
    return any(ships.values())


def now(): return time.time()
