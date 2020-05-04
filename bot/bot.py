import dataclasses
import logging
import random
import sys
import time
import uuid
from typing import List, Union, Dict, Tuple

from bot.eventloop import Scheduler
from bot.protocol import (
    WakeUp,
    NotifyEscapeScheduled,
    NotifyFleetEscaped,
    NotifyFleetRecalled
)
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
    Movement,
    Research
)


class GameState:
    # TODO: GameState will be probably replaced by a wrapper for the OGame client.
    #  The wrapper's primary job will be caching results whenever it's possible and reasonable.

    """ State of global properties for an account. The state should be valid only for a short amount of time
    e.g. during one wakeup call to avoid inconsistencies due to user's actions.

    Furthermore, remember to invalidate cache when changing the state during a wakeup call.
    Currently cache must be invalidating after sending a fleet. """
    def __init__(self, client: OGame):
        self.client = client
        self._planets = None
        self._events = None
        self._movement = None
        self._research = None

    def get_planets(self, invalidate_cache: bool = False) -> List[Planet]:
        """ Get planets from overview page. This method should be called
        first when accessing different state variables. """
        if self._planets is None or invalidate_cache:
            self._planets = self.client.get_planets()
        return self._planets

    def get_events(self, invalidate_cache: bool = False) -> List[FleetEvent]:
        """ Get events by requesting event list. """
        if self._events is None or invalidate_cache:
            self._events = self.client.get_events()
        return self._events

    def get_movement(self,
                     return_fleet: Union[FleetMovement, int] = None,
                     invalidate_cache: bool = False) -> Movement:
        """ Get fleets from movement page. Remember to invalidate cache after sending a fleet. """
        if self._movement is None or invalidate_cache or return_fleet is not None:
            self._movement = self.client.get_fleet_movement(return_fleet)
        return self._movement

    def get_research(self, invalidate_cache: bool = False) -> Research:
        """ Get research from research page. """
        if self._research is None or invalidate_cache:
            self._research = self.client.get_research()
        return self._research


@dataclasses.dataclass
class EscapeFlight:
    dest: Coordinates
    duration: int
    fleet_speed: int
    fuel_consumption: int


class OGameBot:
    def __init__(self, client: OGame, scheduler: Scheduler, **kwargs):
        self.client = client
        self.scheduler = scheduler
        self._listeners = []
        self._engine = None
        self._periodic_wakeup_id = None
        self._earliest_seen_hostile_events = {}  # planet.id -> (planet, earliest_hostile_event)
        self._sleep_min = kwargs.get('sleep_min', 10 * 60)  # 10 minutes
        self._sleep_max = kwargs.get('sleep_max', 15 * 60)  # 15 minutes
        self._min_time_before_attack_to_act = kwargs.get('min_time_before_attack_to_act', 2 * 60)  # 2 minutes
        self._max_time_before_attack_to_act = kwargs.get('max_time_before_attack_to_act', 3 * 60)  # 3 minutes
        self._retry_event_id = uuid.uuid4().hex
        self._exc_retry_delays = [5, 10, 15, 30, 60]  # seconds
        self._exc_count = 0

    def start(self):
        if self._engine is None:
            self._engine = Engine(self._get_server_data())
        if self._periodic_wakeup_id is None:
            def random_sleep_duration(): return random.uniform(self._sleep_min, self._sleep_max)
            self._periodic_wakeup_id = self.scheduler.push(
                delay=0, priority=0, data=WakeUp(), period=random_sleep_duration)

    def stop(self):
        self.scheduler.cancel(self._periodic_wakeup_id)
        self._periodic_wakeup_id = None

    def add_listener(self, listener):
        self._listeners.append(listener)

    def remove_listener(self, listener):
        self._listeners.remove(listener)

    def handle_event(self, event):
        if not self.started:
            raise ValueError('OGameBot has not been started yet.')
        if isinstance(event, WakeUp):
            self._do_work(event)

    @property
    def started(self):
        return self._periodic_wakeup_id is not None

    def _do_work(self, event: WakeUp):
        if self._retrying_after_exception:
            # Ignore any incoming events during retrying after exception. Once the retry event is successful
            #  all the ignored events will be handled simultaneously during handling of that retry event.
            if event.id != self._retry_event_id:
                return
        try:
            state = GameState(self.client)
            self._handle_hostile_events(state)
            self._exc_count = 0
        except Exception:
            retry_delay_index = min(self._exc_count, len(self._exc_retry_delays) - 1)
            retry_delay = self._exc_retry_delays[retry_delay_index]
            retry_event = WakeUp(self._retry_event_id)
            self.scheduler.push(retry_delay, 0, retry_event)
            self._exc_count += 1
            logging.exception(f'Exception thrown {self._exc_count} times during event handling. '
                              f'Retrying in {retry_delay} seconds.')
            self._notify_listeners_exception()
            raise

    def _handle_hostile_events(self, state: GameState):
        exception_raised = False
        planets = state.get_planets()
        events = state.get_events()
        earliest_hostile_events = get_earliest_hostile_events(events, planets)
        # Log fleet events.
        if events:
            logging.debug(f'Fleet events:\n{format_fleet_events(events, planets)}')
            if not earliest_hostile_events:
                logging.info('No hostile fleets on sight. Your planets are safe.')
        else:
            logging.info('No fleet movement has been detected.')
        # Handle hostile events.
        for planet, earliest_hostile_event in earliest_hostile_events.values():
            try:
                earliest_hostile_arrival = earliest_hostile_event.arrival_time
                logging.info(f'Hostile fleet arrives at {planet} on {time.ctime(earliest_hostile_arrival)}')
                # If there is an attack later in the future then schedule an escape event.
                if earliest_hostile_arrival > now() + self._max_time_before_attack_to_act:
                    seen_event_data = self._earliest_seen_hostile_events.get(planet.id)
                    if seen_event_data is None:
                        earliest_seen_hostile_arrival = None
                    else:
                        _, earliest_seen_hostile_event = seen_event_data
                        earliest_seen_hostile_arrival = earliest_seen_hostile_event.arrival_time
                    # Schedule future escape event only if this hostile event has not been seen before
                    #  to avoid repeating the same escape event.
                    if earliest_seen_hostile_arrival is None \
                            or earliest_hostile_arrival == earliest_seen_hostile_arrival:
                        time_before_attack_to_act = random.randint(self._min_time_before_attack_to_act,
                                                                   self._max_time_before_attack_to_act)
                        escape_time = earliest_hostile_arrival - time_before_attack_to_act
                        self.scheduler.pushabs(escape_time, 0, WakeUp())
                        scheduled_escape_log = NotifyEscapeScheduled(
                            planet=planet,
                            hostile_arrival=earliest_hostile_arrival,
                            escape_time=escape_time)
                        logging.info(f'Scheduled escape from {planet} on {time.ctime(escape_time)}')
                        self._notify_listeners(scheduled_escape_log)
                # Otherwise attempt to defend the planet if a hostile fleet arrives soon.
                else:
                    technology = state.get_research().technology
                    resources = self.client.get_resources(planet).amount
                    # It is important that `get_fleet_dispatch` directly precedes `send_fleet`
                    #  to make sure the dispatch token remains valid.
                    fleet_dispatch = self.client.get_fleet_dispatch(planet)
                    # Search for all possible escape flights.
                    escape_flights = get_escape_flights(
                        engine=self._engine,
                        origin=planet,
                        destinations=planets,
                        ships=fleet_dispatch.ships,
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

                    # Pick the cheapest escape flight if such flight exists.
                    cheapest_escape_flight = get_cheapest_flight(escape_flights)
                    fleet_escaped_log = NotifyFleetEscaped(
                        origin=planet,
                        hostile_arrival=earliest_hostile_arrival,
                        destination=match_planet(cheapest_escape_flight.dest, planets))
                    # Make sure there is any fleet on the planet.
                    if ships_exist(fleet_dispatch.ships):
                        # Make sure there are free fleet slots.
                        if fleet_dispatch.free_fleet_slots > 0:
                            if cheapest_escape_flight:
                                deuterium = resources[Resource.deuterium]
                                # Make sure there is enough fuel to send the fleet.
                                if deuterium >= cheapest_escape_flight.fuel_consumption:
                                    # Adjust the available resources by subtracting fuel consumption.
                                    resources[Resource.deuterium] -= cheapest_escape_flight.fuel_consumption
                                    # Select which resources will be saved.
                                    cargo = get_cargo(
                                        engine=self._engine,
                                        resources=resources,
                                        ships=fleet_dispatch.ships,
                                        technology=technology)
                                    # Send fleet to a safe destination.
                                    self.client.send_fleet(
                                        origin=planet,
                                        dest=cheapest_escape_flight.dest,
                                        ships=fleet_dispatch.ships,
                                        mission=Mission.deployment,
                                        fleet_speed=cheapest_escape_flight.fleet_speed,
                                        resources=cargo,
                                        fleet_dispatch=fleet_dispatch)
                                    # Invalidate cache because the game state was altered by sending the fleet.
                                    movement = state.get_movement(invalidate_cache=True)
                                    # Look for the corresponding fleet event to make sure the fleet was sent.
                                    fleets = find_fleets(
                                        fleets=movement.fleets,
                                        dest=cheapest_escape_flight.dest,
                                        mission=Mission.deployment,
                                        departs_before=movement.timestamp + 1,
                                        departs_after=fleet_dispatch.timestamp - 1)
                                    if len(fleets) > 1:
                                        fleet_escaped_log.error = 'Multiple fleets matched.'
                                    else:
                                        fleet_escaped_log.error = 'Failed to find the fleet. ' \
                                                                  'The fleet may have not been dispatched at all.'
                                else:
                                    fleet_escaped_log.error = 'Not enough fuel.'
                            else:
                                fleet_escaped_log.error = 'No escape route.'
                        else:
                            fleet_escaped_log.error = 'No free fleet slots.'
                    else:
                        fleet_escaped_log.error = 'No ships.'
                    if fleet_escaped_log.error:
                        logging.warning(f'Escape from {planet} failed: {fleet_escaped_log.error}')
                    else:
                        logging.info(f'Escape from {planet} was successful')
                    self._notify_listeners(fleet_escaped_log)

                    # Fleets returning to a planet under attack are not considered during fleet saving
                    #  i.e. bot doesn't wait for returning fleets. As long as returning fleet is not being
                    #  deliberately sniped by an opponent, the chances of fleet returning at a time between the
                    #  attack and fleet save are quite low.

                    # Get own fleet movement in case a fleet needs to be returned.
                    movement = state.get_movement()
                    deployment_fleets = find_fleets(
                        fleets=movement.fleets,
                        origin=planets,
                        dest=planet,
                        mission=Mission.deployment)
                    for fleet in deployment_fleets:
                        # Return deployment fleets if the destination is under attack and the fleet arrives
                        #  before the next wake up (+ maximum time the bot has to act in case of an attack).
                        #  This ensures that if the opponent delays the attack,
                        #  she will not be able to snipe the incoming fleet.
                        next_wakeup = now() + self._sleep_max + self._max_time_before_attack_to_act
                        if not fleet.return_flight and fleet.arrival_time <= next_wakeup:
                            movement = state.get_movement(return_fleet=fleet)
                            # Make sure that fleet was sent.
                            fleet = find_fleets(movement.fleets, id=fleet.id)
                            fleet_recalled_log = NotifyFleetRecalled(
                                origin=match_planet(fleet.origin, planets),
                                destination=match_planet(fleet.dest, planets),
                                hostile_arrival=earliest_hostile_arrival)
                            if fleet.return_flight:
                                logging.info(f'Recalling fleet {fleet.id} was successful.')
                            else:
                                fleet_recalled_log.error = 'Failed to return fleet.'
                                logging.warning(f'Failed to return fleet {fleet.id}.')
                            self._notify_listeners(fleet_recalled_log)
            except Exception as e:
                logging.exception(f"Exception occurred while handling hostile events on {planet}")
                self._notify_listeners_exception(e)
                exception_raised = True
        # Update the earliest seen hostile events.
        self._earliest_seen_hostile_events = earliest_hostile_events
        if exception_raised:
            raise ValueError('Exceptions occurred during event handling.')

    def _notify_listeners(self, log):
        """ Notify listeners about actions taken. """
        for listener in self._listeners:
            listener.notify(log)

    def _notify_listeners_exception(self, e=None):
        """ Notify listeners about an exception. By default the last thrown exception is reported. """
        if e is None:
            e = sys.exc_info()
        elif isinstance(e, Exception):
            exc_type = type(e)
            exc_tb = e.__traceback__
            e = (exc_type, e, exc_tb)
        for listener in self._listeners:
            listener.notify_exception(e)

    def _get_server_data(self):
        """ Get server data from OGameAPI. """
        server_number = self.client.server['number']
        server_lang = self.client.server['language']
        api_client = OGameAPI(server_number, server_lang)
        server_data = api_client.get_server_data()['server_data']
        return server_data

    @property
    def _retrying_after_exception(self):
        return self._exc_count > 0


def get_escape_flights(engine: Engine,
                       origin: Union[Planet, Coordinates],
                       destinations: List[Union[Planet, Coordinates]],
                       ships: Dict[Ship, int],
                       technology: Dict[Technology, int] = None) -> List[EscapeFlight]:
    """ Get a list of all possible escape flights from origin. """
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
                flight_duration = engine.flight_duration(
                    distance=distance,
                    ships=ships,
                    fleet_speed=speed_percentage,
                    technology=technology)
                fuel_consumption = engine.fuel_consumption(
                    distance=distance,
                    ships=ships,
                    flight_duration=flight_duration,
                    technology=technology)
                escape_flight = EscapeFlight(
                    dest=destination,
                    duration=flight_duration,
                    fleet_speed=fleet_speed + 1,
                    fuel_consumption=fuel_consumption)
                escape_flights.append(escape_flight)
    return escape_flights


def get_cargo(engine: Engine,
              resources: Dict[Resource, int],
              ships: Dict[Ship, int],
              technology: Dict[Technology, int] = None) -> Dict[Resource, int]:
    """ Get resources that can be loaded on the ships. Priority descending: deuterium, crystal, metal. """
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


def find_fleets(fleets: List[Union[FleetEvent, FleetMovement]],
                id: int = None,
                origin: Union[Planet, Coordinates, List[Union[Planet, Coordinates]]] = None,
                dest: Union[Planet, Coordinates, List[Union[Planet, Coordinates]]] = None,
                mission: Union[Mission, List[Mission]] = None,
                arrives_before: int = None,
                arrives_after: int = None,
                departs_before: int = None,
                departs_after: int = None,
                is_return_flight: bool = None):
    """ Find fleets matching the provided criteria. If looking by `id` a single fleet or None is returned. """
    if origin is not None:
        if not isinstance(origin, list):
            origin = [origin]
        origin = [obj.coords if isinstance(obj, Planet) else obj for obj in origin]
    if dest is not None:
        if not isinstance(dest, list):
            dest = [dest]
        dest = [obj.coords if isinstance(obj, Planet) else obj for obj in dest]
    if mission is not None and not isinstance(mission, list):
        mission = [mission]
    if id is not None:
        return next((fleet for fleet in fleets if fleet.id == id), None)
    return [fleet for fleet in fleets
            if (not origin or fleet.origin in origin)
            and (not dest or fleet.dest in dest)
            and (not mission or fleet.mission in mission)
            and (not arrives_before or fleet.arrival_time < arrives_before)
            and (not arrives_after or fleet.arrival_time > arrives_after)
            and (not departs_before or fleet.departure_time < departs_before)
            and (not departs_after or fleet.departure_time > departs_after)
            and (is_return_flight is None or fleet.return_flight == is_return_flight)]


def get_earliest_hostile_events(events: List[FleetEvent],
                                planets: List[Planet]) -> Dict[int, Tuple[Planet, FleetEvent]]:
    """ Get earliest hostile event for each planet. """
    earliest_hostile_events = {}
    for planet in planets:
        hostile_events = find_fleets(events, dest=planet, mission=[Mission.attack, Mission.acs_attack])
        if hostile_events:
            earliest_hostile_event = get_earliest_fleet(hostile_events)
            earliest_hostile_events[planet.id] = (planet, earliest_hostile_event)
    return earliest_hostile_events


def get_earliest_fleet(fleets: List[Union[FleetEvent, FleetMovement]]) -> Union[FleetEvent, FleetMovement]:
    """ Get the fleet that is arriving first. """
    return min(fleets, key=lambda fleet: fleet.arrival_time) if fleets else None


def get_cheapest_flight(flights: List[EscapeFlight]) -> EscapeFlight:
    """ Get flight which lowest fuel consumption and preferably moons over planets. """
    def priority(flight: EscapeFlight): return (-flight.fuel_consumption,
                                                flight.dest.type == CoordsType.moon)
    return max(flights, key=priority) if flights else None


def ships_exist(ships: Dict[Ship, int]) -> bool:
    """ Check whether there are any ships. """
    return any(ships.values())


def match_planet(coords, planets: List[Planet] = None) -> Planet:
    """ Find planet corresponding to the coordinates. """
    return next((planet for planet in planets if planet.coords == coords), None) or coords if planets else coords


def format_fleet_events(events: List[FleetEvent], planets: List[Planet] = None) -> str:
    def format_event(event: FleetEvent):
        mission = f'{event.mission}{" (R)" if event.return_flight else ""}'
        return f'{time.ctime(event.arrival_time)} | {mission:<16} | ' \
               f'{match_planet(event.origin, planets)} -> {match_planet(event.dest, planets)}'

    events_string = '\n'.join(map(format_event, events))
    return events_string


def now(): return time.time()
