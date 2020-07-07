import dataclasses
import logging
import math
import random
import time
import uuid
from typing import List, Union, Dict, Tuple, Optional, Iterable

from bot.eventloop import Scheduler
from bot.listeners import Listener
from bot.protocol import (
    WakeUp,
    SendExpedition,
    CancelExpedition,
    NotifyHostileEvent,
    NotifyFleetSaved,
    NotifyFleetRecalled,
    NotifyExpeditionFinished,
    NotifyExpeditionCancelled,
    NotifyWakeUp,
    NotifySavedFleetRecalled,
    NotifyPlanetsSafe,
    NotifyHostileEventRecalled,
    NotifyStarted,
    NotifyStopped,
    NotifyDebrisHarvest
)
from ogame import (
    OGame,
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
    Research,
    Overview
)
from ogame.util import ftime


@dataclasses.dataclass(frozen=True)
class EscapeFlight:
    dest: Coordinates
    fleet_speed: int
    fuel_consumption: int
    duration: int
    distance: int


@dataclasses.dataclass
class Expedition:
    data: SendExpedition
    cancelled: CancelExpedition = None
    fleet_id: int = None

    @property
    def running(self): return self.fleet_id is not None


class GameResourceManager:
    """ State of global properties for an account. The state should be valid only for a short amount of time
    e.g. during one wakeup call to avoid inconsistencies due to user's actions.

    Furthermore, remember to invalidate cache when changing the state during a wakeup call.
    Currently cache must be invalidating after sending a fleet. """
    def __init__(self, client: OGame):
        self.client = client
        self._overview = None
        self._events = None
        self._movement = None
        self._research = None

    def get_overview(self, invalidate_cache: bool = False) -> Overview:
        """ Get overview from the landing page. This method should be called
        first when accessing different state variables. """
        if self._overview is None or invalidate_cache:
            self._overview = self.client.get_overview()
        return self._overview

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


class OGameBot:
    def __init__(self,
                 client: OGame,
                 scheduler: Scheduler,
                 sleep_min: int = 600,  # 10 minutes
                 sleep_max: int = 900,  # 15 minutes
                 min_time_before_attack_to_act: int = 120,  # 2 minutes
                 max_time_before_attack_to_act: int = 180,  # 3 minutes
                 try_recalling_saved_fleet: bool = False,
                 max_return_flight_time: int = 600,  # 10 minutes
                 harvest_expedition_debris: bool = True,
                 harvest_speed: int = 10):
        self.client = client
        self.scheduler = scheduler
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self.min_time_before_attack_to_act = min_time_before_attack_to_act
        self.max_time_before_attack_to_act = max_time_before_attack_to_act
        self.try_recalling_saved_fleet = try_recalling_saved_fleet
        self.max_return_flight_time = max_return_flight_time
        self.harvest_expedition_debris = harvest_expedition_debris
        self.harvest_speed = harvest_speed

        self._engine = None
        self._periodic_wakeup_id = None
        self._retry_event_id = uuid4()
        self._exc_retry_delays = [5, 10, 15, 30, 60]  # seconds
        self._exc_count = 0

        self._listeners: List[Listener] = []
        self._last_scheduled_fs: Optional[Tuple[str, str]] = None  # (id from the scheduler, id from the bot)
        self._last_seen_hostile_events: Dict[int, FleetEvent] = {}  # fleet_event.id -> fleet_event
        self._expeditions: Dict[str, Expedition] = {}  # expedition.id -> expedition
        self._saved_fleets: Dict[int, Planet] = {}  # fleet.id -> origin

    def start(self):
        if self._engine is None:
            server_data = self.client.server_data or self.client.api.get_server_data()['server_data']
            self._engine = Engine(server_data)
        if self._periodic_wakeup_id is None:
            def random_sleep_duration(): return random.uniform(self.sleep_min, self.sleep_max)
            self._periodic_wakeup_id = self.scheduler.push(
                delay=0,
                priority=0,
                data=WakeUp(),
                period=random_sleep_duration)
            self._notify_listeners(NotifyStarted())

    def stop(self):
        self.scheduler.cancel(self._periodic_wakeup_id)
        self._periodic_wakeup_id = None
        self._notify_listeners(NotifyStopped())

    def add_listener(self, listener):
        self._listeners.append(listener)

    def remove_listener(self, listener):
        self._listeners.remove(listener)

    def handle_work(self, work):
        if not self.started:
            raise ValueError('OGameBot has not been started yet.')
        if isinstance(work, WakeUp):
            self._do_work(work)
        elif isinstance(work, SendExpedition):
            if work.id in self._expeditions:
                logging.warning(f'Duplicate expedition: {work.id}')
            else:
                self._expeditions[work.id] = Expedition(data=work)
        elif isinstance(work, CancelExpedition):
            if work.id in self._expeditions:
                self._expeditions[work.id].cancelled = work
            else:
                logging.warning(f'Unknown expedition: {work.id}')

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
            self._notify_listeners(NotifyWakeUp())
            resource_manager = GameResourceManager(self.client)
            # Always get the latest overview.
            overview = resource_manager.get_overview()
            # Update the character class in the engine.
            self._engine.character_class = overview.character_class
            # Handle work now.
            # Begin with checking for hostile events and defending planets.
            self._handle_hostile_events(event, resource_manager)
            # Run expeditions.
            if self._expeditions:
                self._handle_expeditions(resource_manager)
            # No exception has been thrown, so reset the exception count.
            self._exc_count = 0
        except Exception as e:
            retry_delay_index = min(self._exc_count, len(self._exc_retry_delays) - 1)
            retry_delay = self._exc_retry_delays[retry_delay_index]
            retry_event = WakeUp(self._retry_event_id)
            self.scheduler.push(retry_delay, 0, retry_event)
            self._exc_count += 1
            logging.exception(f'Exception thrown {self._exc_count} times during event handling. '
                              f'Retrying in {retry_delay} seconds.')
            self._notify_listeners_exception(e)
            raise

    def _handle_hostile_events(self, wakeup: WakeUp, resource_manager: GameResourceManager):
        overview = resource_manager.get_overview()
        events = resource_manager.get_events()
        # Get all hostile fleets.
        hostile_events = find_hostile_events(
            events=events,
            planets=overview.planets)
        hostile_events = {event.id: event for event in hostile_events}
        # Get a list of earliest hostile event per planet.
        hostile_events_per_planet = get_earliest_fleet_per_destination(hostile_events.values())
        # Get the hostile fleet that arrives first.
        earliest_hostile_event = get_earliest_fleet(hostile_events.values())
        # Get a dictionary of the latest friendly arrivals per hostile event. These times are selected based on the
        #  last incoming fleet to the planet under attack. The bot will try waiting for this fleet before saving
        #  the planet. If there is no entry for a given hostile event, it means that the bot is free to choose
        #  when to save the planet.
        # Note that the following holds:
        #  max(last_friendly_arrivals[e.id]) <= e.arrival_time
        last_friendly_arrivals: Dict[int, int] = {}  # hostile_event.id -> last_friendly_arrival
        def arrival_time(e: FleetEvent): return e.arrival_time
        for hostile_event in sorted(hostile_events.values(), key=arrival_time):
            returning_fleets = find_fleets(
                fleets=events,
                origin=hostile_event.dest,
                is_return_flight=True,
                arrives_after=hostile_event.arrival_time - self.max_time_before_attack_to_act,
                arrives_before=hostile_event.arrival_time)
            deployment_fleets = find_fleets(
                fleets=events,
                origin=overview.planets,
                dest=hostile_event.dest,
                mission=Mission.deployment,
                arrives_after=hostile_event.arrival_time - self.max_time_before_attack_to_act,
                arrives_before=hostile_event.arrival_time)
            incoming_fleets = returning_fleets + deployment_fleets
            last_incoming_fleet = get_latest_fleet(incoming_fleets)
            if last_incoming_fleet:
                last_friendly_arrivals[hostile_event.id] = last_incoming_fleet.arrival_time
        # Get a copy of previously seen hostile events.
        last_seen_hostile_events = dict(self._last_seen_hostile_events)
        # Update last seen hostile events.
        self._last_seen_hostile_events = hostile_events
        current_time = now()

        # Notify user about hostile fleets that have been recalled.
        for previous_hostile_event in last_seen_hostile_events.values():
            if previous_hostile_event.id not in hostile_events and previous_hostile_event.arrival_time > current_time:
                planet = match_planet(
                    coords=previous_hostile_event.dest,
                    planets=overview.planets)
                self._notify_listeners(
                    NotifyHostileEventRecalled(
                        planet=planet,
                        hostile_arrival=previous_hostile_event.arrival_time))
        # Notify user about current events.
        if events:
            logging.debug(f'Fleet events:\n{format_fleet_events(events, overview.planets)}')
            if hostile_events:
                for hostile_event in hostile_events.values():
                    planet = match_planet(
                        coords=hostile_event.dest,
                        planets=overview.planets)
                    previous_event_state = last_seen_hostile_events.get(hostile_event.id)
                    # Notify user of this hostile event if it was previously not seen,
                    #  or the opponent has delayed the attack.
                    if not previous_event_state:
                        self._notify_listeners(
                            NotifyHostileEvent(
                                planet=planet,
                                hostile_arrival=hostile_event.arrival_time))
                    elif hostile_event.arrival_time != previous_event_state.arrival_time:
                        self._notify_listeners(
                            NotifyHostileEvent(
                                planet=planet,
                                hostile_arrival=hostile_event.arrival_time,
                                previous_hostile_arrival=previous_event_state.arrival_time))
                    logging.info(f'Hostile fleet arrives at {planet} on {ftime(hostile_event.arrival_time)}')
            else:
                if last_seen_hostile_events:
                    self._notify_listeners(NotifyPlanetsSafe())
                logging.info('No hostile fleets on sight. Your planets are safe.')
        else:
            logging.info('No fleet movement has been detected.')

        if self._last_scheduled_fs:
            scheduled_id, wakeup_id = self._last_scheduled_fs
            # If we are currently not handling this event, then cancel it because we may update our schedule.
            if wakeup.id != wakeup_id:
                self.scheduler.cancel(scheduled_id)
            self._last_scheduled_fs = None
        # If there is a hostile fleet approaching we have to update our schedule.
        if earliest_hostile_event:
            wakeup_times = []
            # Determine the earliest event that the bot must respond to.
            for hostile_event in hostile_events.values():
                hostile_arrival = hostile_event.arrival_time
                if current_time < hostile_arrival - self.max_time_before_attack_to_act:
                    # There is plenty of time so schedule a future escape event.
                    last_friendly_arrival = hostile_arrival - random.randint(self.min_time_before_attack_to_act,
                                                                             self.max_time_before_attack_to_act)
                    wakeup_times.append(last_friendly_arrival)
                else:
                    # Hostile fleet is arriving shortly so make sure to pick up incoming fleets if there are any,
                    #  otherwise schedule a check-up after the attack to assess the situation.
                    last_friendly_arrival = last_friendly_arrivals.get(hostile_event.id)
                    if last_friendly_arrival:
                        # Only wait for the incoming fleets for up to 5 seconds before the hostile arrival.
                        #  However, if the hostile fleet arrives in less than 5 seconds and there is still
                        #  a friendly fleet returning, then try to save it too.
                        if current_time < (hostile_arrival - 10) < (last_friendly_arrival - 1):
                            wakeup_times.append(hostile_arrival - 10)
                        else:
                            wakeup_times.append(last_friendly_arrival + 1)
                    else:
                        # We will handle this hostile event further down in the function
                        #  so schedule a check-up after hostile fleet arrives.
                        wakeup_times.append(hostile_arrival + 1)
            # Pick the earliest wake-up time and make sure it is in the future.
            earliest_wakeup_time = min([t for t in wakeup_times if current_time < t], default=None)
            if earliest_wakeup_time:
                wakeup_id = uuid4()
                scheduled_id = self.scheduler.pushabs(
                    abstime=earliest_wakeup_time,
                    priority=0,
                    data=WakeUp(wakeup_id))
                self._last_scheduled_fs = (scheduled_id, wakeup_id)
                logging.info(f'Defensive wake-up now scheduled on {ftime(earliest_wakeup_time)}')

        # Handle immediate hostile events.
        for hostile_event in sorted(hostile_events_per_planet, key=arrival_time):
            # Mimic the scheduling of an escape flight to determine the time of fs.
            hostile_arrival = hostile_event.arrival_time
            earliest_save_time = hostile_arrival - self.max_time_before_attack_to_act
            if current_time < earliest_save_time:
                continue  # ignore this event for now if it is not the time to save yet
            planet = match_planet(
                coords=hostile_event.dest,
                planets=overview.planets)
            fs_notification = NotifyFleetSaved(
                origin=planet,
                hostile_arrival=hostile_arrival)
            # Get additional information to better prepare escape flights.
            technology = resource_manager.get_research().technology
            resources = self.client.get_resources(planet).amount
            deuterium = resources.setdefault(Resource.deuterium, 0)
            # Go to the fleet dispatch page. It is important that `get_fleet_dispatch`
            #  directly precedes `send_fleet` to make sure the dispatch token remains valid.
            fleet_dispatch = self.client.get_fleet_dispatch(planet)
            # Make sure there are any ships on the planet.
            if not ships_exist(fleet_dispatch.ships):
                logging.warning(f'Escape from {planet} failed because there are no ships.')
                fs_notification.error = 'No ships on the planet.'
                self._notify_listeners(fs_notification)
                continue
            # Make sure there are free fleet slots.
            if fleet_dispatch.free_fleet_slots == 0:
                logging.warning(f'Escape from {planet} failed because there are no free fleet slots.')
                fs_notification.error = 'No free fleet slots.'
                self._notify_listeners(fs_notification)
                continue
            # Search for all possible escape flights.
            escape_flights = get_escape_flights(
                engine=self._engine,
                origin=planet,
                destinations=overview.planets,
                ships=fleet_dispatch.ships,
                technology=technology)
            # Make sure there are any escape flights.
            if not escape_flights:
                logging.warning(f'Escape from {planet} failed because there are no escape routes.')
                fs_notification.error = 'No escape route.'
                self._notify_listeners(fs_notification)
                continue
            # Sort escape flight according to predefined safety rules (safest first).
            escape_flights = sort_escape_flights_by_safety(
                escape_flights=escape_flights,
                hostile_events=list(hostile_events.values()),
                max_time_before_attack_to_act=self.max_time_before_attack_to_act)
            # From the sorted list of flights pick the first for which there is enough fuel.
            escape_flight = next((flight for flight in escape_flights
                                  if flight.fuel_consumption <= deuterium), None)
            # Make sure there is enough fuel.
            if not escape_flight:
                logging.warning(f'Escape from {planet} failed because there is not enough fuel.')
                fs_notification.error = 'Not enough fuel.'
                self._notify_listeners(fs_notification)
                continue
            # A viable escape route has been found so send the fleet now.
            # Store destination in the log.
            destination = match_planet(
                coords=escape_flight.dest,
                planets=overview.planets)
            fs_notification.destination = destination
            # Adjust the available resources by subtracting fuel consumption.
            resources[Resource.deuterium] -= escape_flight.fuel_consumption
            # Select which resources will be saved.
            free_cargo_capacity = self._engine.cargo_capacity(
                ships=fleet_dispatch.ships,
                technology=technology)
            cargo = get_cargo(
                resources=resources,
                free_cargo_capacity=free_cargo_capacity)
            # Send fleet to a safe destination.
            success = self.client.send_fleet(
                origin=planet,
                dest=escape_flight.dest,
                ships=fleet_dispatch.ships,
                mission=Mission.deployment,
                fleet_speed=escape_flight.fleet_speed,
                resources=cargo,
                token=fleet_dispatch.dispatch_token)
            if success:
                logging.info(f'Fleet successfully escaped from {planet} to {destination}.')
            else:
                logging.warning(f'Failed to save fleet from an attack on {planet}.')
                fs_notification.error = 'Failed to send fleet.'
                self._notify_listeners(fs_notification)
                continue
            # Invalidate cache because the game state was altered by sending the fleet.
            movement = resource_manager.get_movement(invalidate_cache=True)
            # Find the saved fleet to allow tracking.
            fleets = find_fleets(
                fleets=movement.fleets,
                origin=planet,
                dest=escape_flight.dest,
                mission=Mission.deployment,
                ships=fleet_dispatch.ships,
                cargo=cargo,
                departs_before=movement.timestamp + 1,
                departs_after=fleet_dispatch.timestamp - 1)
            if len(fleets) == 0:
                logging.warning('Failed to find saved fleet.')
                fs_notification.error = 'Failed to find the fleet.'
            elif len(fleets) == 1:
                # The fleet has been successfully saved.
                if self.try_recalling_saved_fleet:
                    saved_fleet = fleets[0]
                    self._saved_fleets[saved_fleet.id] = planet
            elif len(fleets) > 1:
                logging.warning('Multiple fleets matched the saved fleet.')
                fs_notification.error = 'Multiple fleets matched.'
            self._notify_listeners(fs_notification)

        # Return deployment fleets if the destination is under attack and the fleet arrives
        #  within 5 seconds of the attack. This ensures that if the opponent delays the attack,
        #  she will not be able to snipe the incoming fleet.
        for hostile_event in sorted(hostile_events_per_planet, key=arrival_time):
            hostile_arrival = hostile_event.arrival_time
            earliest_save_time = hostile_arrival - self.max_time_before_attack_to_act
            if current_time < earliest_save_time:
                continue  # ignore this event for now if it is not the time to save yet
            planet = match_planet(
                coords=hostile_event.dest,
                planets=overview.planets)
            movement = resource_manager.get_movement()
            deployment_fleets = find_fleets(
                fleets=movement.fleets,
                origin=overview.planets,
                dest=planet,
                mission=Mission.deployment,
                is_return_flight=False)
            for deployment_fleet in deployment_fleets:
                # Note that `arrival_time` in the fleet movement means the arrival on the origin planet.
                deployment_arrival = deployment_fleet.departure_time + deployment_fleet.flight_duration
                if (hostile_arrival - 10) <= deployment_arrival <= (hostile_arrival + 10):
                    movement = resource_manager.get_movement(return_fleet=deployment_fleet)
                    # Make sure that the fleet was returned.
                    deployment_fleet = find_fleets(
                        fleets=movement.fleets,
                        id=deployment_fleet.id)
                    fleet_recalled_notification = NotifyFleetRecalled(
                        origin=match_planet(deployment_fleet.origin, overview.planets),
                        destination=match_planet(deployment_fleet.dest, overview.planets),
                        hostile_arrival=hostile_arrival)
                    if deployment_fleet.return_flight:
                        logging.info(f'Recalling deployment fleet to {planet} was successful.')
                    else:
                        fleet_recalled_notification.error = 'Failed to return fleet.'
                        logging.warning(f'Failed to recall deployment fleet to {planet}.')
                    self._notify_listeners(fleet_recalled_notification)

        # Try recalling saved fleets. The requirement is that once recalled, the fleet must arrive
        #  in less than `sleep_min` time. Thus, the bot only handles short-term recalling. This is to ensure
        #  that the fleet can be properly saved in the future.
        # Operate on a copy to allow mutation of the original.
        for saved_fleet_id, origin in dict(self._saved_fleets).items():
            incoming_hostile_fleets = find_fleets(
                fleets=list(hostile_events.values()),
                dest=origin)
            # Make sure that the origin is not under attack
            if incoming_hostile_fleets:
                # Wait for the next wake-up to see whether fleet can be recalled.
                continue
            movement = resource_manager.get_movement()
            saved_fleet = find_fleets(
                fleets=movement.fleets,
                id=saved_fleet_id)
            fs_recalled_notification = NotifySavedFleetRecalled(origin=origin)
            # Make sure that the fleet is still flying.
            if not saved_fleet:
                self._saved_fleets.pop(saved_fleet_id)
                logging.warning(f'Fleet escaping from {origin} is not flying anymore.')
                fs_recalled_notification.error = 'Fleet not flying anymore.'
                self._notify_listeners(fs_recalled_notification)
                continue
            # Make sure that fleet is not already returning.
            if saved_fleet.return_flight:
                self._saved_fleets.pop(saved_fleet_id)
                logging.warning(f'Fleet escaping from {origin} is already returning.')
                fs_recalled_notification.error = 'Fleet already returning.'
                self._notify_listeners(fs_recalled_notification)
                continue
            # Make sure that if the fleet is returned, it will arrive in less than `max_return_flight_time` seconds.
            current_flight_duration = now() - saved_fleet.departure_time
            if current_flight_duration > self.max_return_flight_time:
                self._saved_fleets.pop(saved_fleet_id)
                logging.warning(f'Cannot recall fleet escaping from {origin} because it would arrive too late.')
                fs_recalled_notification.error = 'Fleet would arrive too late.'
                self._notify_listeners(fs_recalled_notification)
                continue
            # If all the above requirements are met, the fleet can be safely returned
            movement = resource_manager.get_movement(return_fleet=saved_fleet_id)
            # Make sure that fleet was returned.
            saved_fleet = find_fleets(movement.fleets, id=saved_fleet_id)
            if saved_fleet.return_flight:
                self._saved_fleets.pop(saved_fleet_id)
                logging.info(f'Fleet that escaped from {origin} was successfully recalled.')
            else:
                logging.warning(f'Failed to recall fleet that escaped from {origin}.')
                fs_recalled_notification.error = 'Failed to recall fleet.'
            self._notify_listeners(fs_recalled_notification)

    def _handle_expeditions(self, resource_manager: GameResourceManager):
        overview = resource_manager.get_overview()
        events = resource_manager.get_events()
        movement = resource_manager.get_movement()
        # Find finished expeditions based on the current movement.
        finished_expeditions = [expedition for expedition in self._expeditions.values()
                                if not find_fleets(movement.fleets, id=expedition.fleet_id)
                                or expedition.cancelled]
        # Remove cancelled expeditions. The remaining expeditions are either repeated or completed.
        for expedition in finished_expeditions:
            if expedition.cancelled:
                fleet_returned = False
                if expedition.cancelled.return_fleet:
                    fleet = find_fleets(movement.fleets, id=expedition.fleet_id)
                    if not fleet.holding and not fleet.return_flight:
                        # Recall expedition fleet.
                        movement = resource_manager.get_movement(return_fleet=expedition.fleet_id)
                        fleet = find_fleets(movement.fleets, id=expedition.fleet_id)
                        fleet_returned = fleet.return_flight
                    if fleet_returned:
                        logging.info(f'Expedition cancelled successfully and fleet recalled: {expedition.data}')
                    else:
                        logging.info(f'Expedition cancelled successfully '
                                     f'but fleet could not be recalled: {expedition.data}')
                else:
                    logging.info(f'Expedition cancelled successfully: {expedition.data}')
                # Remove cancelled expedition.
                self._expeditions.pop(expedition.data.id)
                expedition_log = NotifyExpeditionCancelled(
                    expedition=expedition.data,
                    cancellation=expedition.cancelled,
                    fleet_returned=fleet_returned)
                self._notify_listeners(expedition_log)
            elif expedition.data.repeat == 0:
                # Expedition has finished and now remove it.
                self._expeditions.pop(expedition.data.id)
                logging.info(f'Expedition finished: {expedition.data}')
                expedition_log = NotifyExpeditionFinished(expedition=expedition.data)
                self._notify_listeners(expedition_log)
            else:
                # Expedition has finished but repeat it.
                expedition.fleet_id = None

        # After cleaning up the expeditions, the only ones that are left at this point
        #  are expeditions that are either running or scheduled to run next. Therefore,
        #  this is the perfect time to find any unassigned expeditions from the fleet
        #  movement and attempt to match it with an expedition that is scheduled to run.
        #
        # Look for any unassigned expedition fleets i.e. currently flying expeditions fleets
        #  that are not matched with any expedition event that the bot received. This could be caused
        #  by the user sending an expedition, or by some failure that prevented the bot from matching
        #  an expedition fleet after sending it with the corresponding expedition event.
        def get_unassigned_expedition_fleets(fleets, expeditions):
            assigned_fleet_ids = [expedition.fleet_id for expedition in expeditions if expedition.running]
            return [fleet for fleet in fleets
                    if fleet.mission == Mission.expedition
                    and fleet.id not in assigned_fleet_ids]

        for expedition in self._expeditions.values():
            # Attempt to match this expedition event with any unassigned expedition fleet.
            unassigned_expedition_fleets = get_unassigned_expedition_fleets(
                fleets=movement.fleets,
                expeditions=self._expeditions.values())
            matched_unassigned_expedition_fleet = find_fleets(
                fleets=unassigned_expedition_fleets,
                origin=expedition.data.origin,
                dest=expedition.data.dest,
                mission=Mission.expedition,
                ships=expedition.data.ships)
            if matched_unassigned_expedition_fleet:
                expedition_fleet = matched_unassigned_expedition_fleet[0]
                expedition.fleet_id = expedition_fleet.id
                logging.info(f'Expedition has been matched with a fleet: {expedition.data}')

        # Try running as many new expeditions as possible.
        for expedition in list(self._expeditions.values()):  # operate on a copy to allow mutation of the original
            planet = match_planet(expedition.data.origin, overview.planets)
            if not planet:
                # Expedition is invalid because of wrong origin (not one of user's planets).
                self._expeditions.pop(expedition.data.id)
                logging.warning(f'Invalid expedition origin. Removing expedition: {expedition.data}')
                expedition_log = NotifyExpeditionFinished(
                    expedition=expedition.data,
                    error='Invalid expedition origin.')
                self._notify_listeners(expedition_log)
                continue
            if expedition.running:
                continue  # expedition is already running so we don't have to do anything
            # Make sure there are enough slots to send the expedition fleet.
            if movement.free_fleet_slots == 0 or movement.free_expedition_slots == 0:
                logging.warning(f'No free slots for expeditions.')
                break
            # Expeditions from planets under attack will be postponed.
            incoming_hostile_fleets = find_hostile_events(
                events=events,
                planets=planet)
            if incoming_hostile_fleets:
                logging.warning(f'Origin is currently under attack. Postponing expedition: {expedition.data}')
                continue
            # Get additional information to better prepare the expeditions.
            technology = resource_manager.get_research().technology
            resources = self.client.get_resources(planet).amount
            deuterium = resources.setdefault(Resource.deuterium, 0)
            # Check if the required ships are available.
            fleet_dispatch = self.client.get_fleet_dispatch(planet)
            if not enough_ships(available_ships=fleet_dispatch.ships, required_ships=expedition.data.ships):
                logging.warning(f'The required ships are not available. Postponing expedition: {expedition.data}')
                continue
            # Check if the required cargo is available.
            cargo = expedition.data.cargo or {}
            required_capacity = sum(cargo.values())
            fleet_capacity = self._engine.cargo_capacity(
                ships=expedition.data.ships,
                technology=technology)
            if required_capacity > fleet_capacity:
                # Expedition is invalid because the fleet does not have enough capacity to take the cargo.
                self._expeditions.pop(expedition.data.id)
                logging.warning(f'Not enough capacity for the cargo. Removing expedition: {expedition.data}')
                expedition_log = NotifyExpeditionFinished(
                    expedition=expedition.data,
                    error='Not enough capacity for the cargo.')
                self._notify_listeners(expedition_log)
                continue
            resources_available = True
            for resource, amount in cargo.items():
                available_resource = resources.setdefault(resource, 0)
                if available_resource < amount:
                    resources_available = False
                    break
            if not resources_available:
                logging.warning(f'Not enough resources for the required cargo. '
                                f'Postponing expedition: {expedition.data}')
                continue
            # Check if there is enough fuel to make the flight.
            fuel_consumption = get_fuel_consumption(
                engine=self._engine,
                origin=planet,
                destination=expedition.data.dest,
                ships=expedition.data.ships,
                technology=technology,
                fleet_speed=expedition.data.speed,
                holding_time=expedition.data.holding_time)
            deuterium_after_cargo = deuterium - cargo.get(Resource.deuterium, 0)
            if deuterium_after_cargo < fuel_consumption:
                logging.warning(f'Not enough fuel to start the flight. Postponing expedition: {expedition.data}')
                continue
            # Send fleet for expeditions. If an exception is thrown by either `send_fleet`
            #  or `get_movement` then this expedition will not be tracked at first - bot will
            #  assume that it has to be sent again unless it is matched against an unassigned expedition.
            success = self.client.send_fleet(
                origin=planet,
                dest=expedition.data.dest,
                mission=Mission.expedition,
                ships=expedition.data.ships,
                fleet_speed=expedition.data.speed,
                resources=cargo,
                holding_time=expedition.data.holding_time,
                token=fleet_dispatch.dispatch_token)
            if success:
                # Update the counter.
                if expedition.data.repeat != 'forever':
                    expedition.data.repeat -= 1
                logging.info(f'Expedition sent: {expedition.data}')
            else:
                # Remove expedition.
                self._expeditions.pop(expedition.data.id)
                logging.warning(f'Failed to send expedition fleet. Removing expedition: {expedition.data}')
                expedition_log = NotifyExpeditionFinished(
                    expedition=expedition.data,
                    error='Failed to send the expedition fleet.')
                self._notify_listeners(expedition_log)
                continue
            # Invalidate cache because the game state was altered by sending the fleet.
            movement = resource_manager.get_movement(invalidate_cache=True)
            # Find the id of the expedition fleet to allow tracking.
            unassigned_expedition_fleets = get_unassigned_expedition_fleets(
                fleets=movement.fleets,
                expeditions=self._expeditions.values())
            fleets = find_fleets(
                fleets=unassigned_expedition_fleets,
                origin=planet,
                dest=expedition.data.dest,
                mission=Mission.expedition,
                ships=expedition.data.ships,
                cargo=cargo,
                departs_before=movement.timestamp + 1,
                departs_after=fleet_dispatch.timestamp - 1)
            if len(fleets) == 0:
                logging.warning(f'Failed to find the expedition fleet: {expedition.data}')
            elif len(fleets) == 1:
                # Assign fleet to the expedition.
                expedition.fleet_id = fleets[0].id
            else:
                logging.warning(f'Multiple fleets matched the expedition: {expedition.data}')

        # Check for any expedition debris to harvest.
        if self.harvest_expedition_debris:
            expedition_destinations = {expedition.data.dest for expedition in self._expeditions.values()}
            for destination in expedition_destinations:
                galaxy = self.client.get_galaxy(
                    galaxy=destination.galaxy,
                    system=destination.system)
                # First check whether there is any debris from expeditions.
                if galaxy.expedition_debris:
                    required_pathfinders = None
                    # Find all origins that are connected to this destination.
                    expedition_origins = {expedition.data.origin for expedition in self._expeditions.values()
                                          if expedition.data.dest == destination}
                    # Set destination to debris.
                    destination = dataclasses.replace(destination, type=CoordsType.debris)
                    def distance(coords): return self._engine.distance(coords, destination)
                    # Try to send pathfinders starting from the closest origin.
                    for origin_coords in sorted(expedition_origins, key=distance):
                        # Find out how much cargo can a single pathfinder carry.
                        technology = resource_manager.get_research().technology
                        pathfinder_cargo = self._engine.cargo_capacity(
                            ships=Ship.pathfinder,
                            technology=technology)
                        # Calculate how many pathfinders are required to harvest the entire expedition debris.
                        required_cargo = sum(galaxy.expedition_debris.values())
                        required_pathfinders = math.ceil(required_cargo / pathfinder_cargo)
                        # Check for any pathfinder fleets already flying towards the debris.
                        harvesting_fleets = find_fleets(
                            fleets=movement.fleets,
                            dest=destination,
                            mission=Mission.harvest,
                            is_return_flight=False)
                        for harvesting_fleet in harvesting_fleets:
                            # Note that we are assuming that the harvesting fleet has no cargo!
                            required_pathfinders -= harvesting_fleet.ships.get(Ship.pathfinder, 0)
                        if required_pathfinders <= 0:
                            break  # we don't need to send any more pathfinders to this destination
                        # Get additional information about the origin planet.
                        origin = match_planet(
                            coords=origin_coords,
                            planets=overview.planets)
                        resources = self.client.get_resources(origin).amount
                        deuterium = resources.setdefault(Resource.deuterium, 0)
                        fleet_dispatch = self.client.get_fleet_dispatch(origin)
                        # Try sending as many pathfinders as possible.
                        # Note that the actual fuel consumption per pathfinder is slightly lower when flying in a fleet.
                        single_pf_fuel_consumption = get_fuel_consumption(
                            engine=self._engine,
                            origin=origin,
                            destination=destination,
                            ships={Ship.pathfinder: 1},
                            technology=technology,
                            fleet_speed=self.harvest_speed)
                        # Get the number of available pathfinders based on available fuel and ships.
                        available_pathfinders = min(
                            fleet_dispatch.ships.get(Ship.pathfinder, 0),
                            deuterium // single_pf_fuel_consumption)
                        if not available_pathfinders:
                            continue  # we cannot send any pathfinders from this planet
                        pathfinder_fleet = {Ship.pathfinder: min(required_pathfinders, available_pathfinders)}
                        success = self.client.send_fleet(
                            origin=origin,
                            dest=destination,
                            mission=Mission.harvest,
                            ships=pathfinder_fleet,
                            fleet_speed=self.harvest_speed,
                            token=fleet_dispatch.dispatch_token)
                        if success:
                            sent_pathfinders = pathfinder_fleet[Ship.pathfinder]
                            required_pathfinders -= sent_pathfinders
                            logging.info(f'Sent {sent_pathfinders} pathfinders '
                                         f'from {origin} to {destination}.')
                        else:
                            logging.warning(f'Failed to send pathfinders from {origin} to '
                                            f'harvest expedition debris at {destination}.')
                            continue
                        # Invalidate cache because the game state was altered by sending the fleet.
                        movement = resource_manager.get_movement(invalidate_cache=True)
                    if required_pathfinders > 0:
                        logging.warning(f'Missing {required_pathfinders} pathfinders to fully '
                                        f'harvest expedition debris at {destination}.')
                        self._notify_listeners(
                            NotifyDebrisHarvest(
                                destination=destination,
                                debris=galaxy.expedition_debris,
                                error=f'Missing {required_pathfinders} to fully harvest expedition debris'))

    def _notify_listeners(self, notification):
        """ Notify listeners about actions taken. """
        for listener in self._listeners:
            listener.notify(notification)

    def _notify_listeners_exception(self, e):
        """ Notify listeners about an exception. By default the last thrown exception is reported. """
        for listener in self._listeners:
            listener.notify_exception(e)

    @property
    def _retrying_after_exception(self):
        return self._exc_count > 0


def find_hostile_events(events: List[FleetEvent],
                        planets: Union[Planet, List[Planet]]) -> List[FleetEvent]:
    def only_probes(e: FleetEvent) -> bool:
        # Check if there is information about ships and whether probe is the only ship type in the fleet.
        return e.ships and Ship.espionage_probe in e.ships and len(e.ships) == 1
    hostile_events = find_fleets(
        fleets=events,
        dest=planets,
        mission=[Mission.attack,        # standard attack mission
                 Mission.acs_attack,    # ACS attack mission
                 Mission.destroy,       # attack on a destroy mission
                 Mission.espionage])    # attack on an espionage mission
    # Filter hostile events with only probes in the fleet.
    hostile_events = [e for e in hostile_events if not only_probes(e)]
    return hostile_events


def sort_escape_flights_by_safety(escape_flights: List[EscapeFlight],
                                  hostile_events: List[FleetEvent],
                                  max_time_before_attack_to_act: int):
    """ Sort escape flights according to criteria that ensure a safe flight. """
    def safety(flight: EscapeFlight):  # lower is better
        # Why all destinations under attack, where the hostile fleets arrive
        #  before our deployment, are not discarded? First, that would not work
        #  flawlessly e.g. what if all destinations meet the requirements to be discarded.
        #  Second, if need be, escaping fleet might be returned later. In this case,
        #  a smart opponent who knows how this bot works will force a return and attempt to snipe
        #  the returning fleet. This is possible but chances of this happening are very slim,
        #  especially, since this bot is designed to save the fleet if the user fails to do so.
        #  In that context, it's the user's responsibility to react to a hostile event first.
        #  Furthermore, taking these additional precautions may cause a significantly higher
        #  fuel consumption.
        incoming_hostile_fleets = find_fleets(
            fleets=hostile_events,
            dest=flight.dest)
        earliest_hostile_fleet = get_earliest_fleet(incoming_hostile_fleets)
        if earliest_hostile_fleet:
            # Make sure escaping fleet arrives at destination that is under attack only if
            #  it will arrive before the escape from the destination is handled.
            # This is only relevant for planets with moons. In any other case fleet will be sent
            #  to a planet even if it under attack.
            arrival_at_destination = current_time + flight.duration
            earliest_save_time = earliest_hostile_fleet.arrival_time - max_time_before_attack_to_act
            hostile_event_before_arrival = earliest_save_time < arrival_at_destination
        else:
            hostile_event_before_arrival = False
        return (hostile_event_before_arrival if flight.distance == 5 else False,
                flight.distance,  # closer destinations are preferred
                flight.dest.type == CoordsType.planet,  # moons are preferred
                # prefer faster flights if flying between planet and moon in the same system position,
                #  otherwise prefer lesser fuel consumption
                flight.duration if flight.distance == 5 else flight.fuel_consumption)
    current_time = now()
    return sorted(escape_flights, key=safety)


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
            for fleet_speed in range(10):
                distance = engine.distance(origin, destination)
                flight_duration = engine.flight_duration(
                    distance=distance,
                    ships=ships,
                    fleet_speed=fleet_speed + 1,
                    technology=technology)
                fuel_consumption = engine.flight_fuel_consumption(
                    distance=distance,
                    ships=ships,
                    flight_duration=flight_duration,
                    technology=technology)
                escape_flight = EscapeFlight(
                    dest=destination,
                    fleet_speed=fleet_speed + 1,
                    fuel_consumption=fuel_consumption,
                    duration=flight_duration,
                    distance=distance)
                escape_flights.append(escape_flight)
    return escape_flights


def get_fuel_consumption(engine,
                         origin: Union[Planet, Coordinates],
                         destination: Union[Planet, Coordinates],
                         ships: Dict[Ship, int],
                         technology: Dict[Technology, int] = None,
                         fleet_speed: int = 10,
                         holding_time: int = 0) -> int:
    """
    @param engine: game engine
    @param origin: origin coordinates
    @param destination: destination coordinates
    @param ships: dictionary describing the size of the fleet
    @param technology: dictionary describing the current technology levels
    @param fleet_speed: fleet speed (1-10)
    @param holding_time: holding duration in hours
    @return: fuel consumption of a flight
    """
    distance = engine.distance(origin, destination)
    flight_duration = engine.flight_duration(
        distance=distance,
        ships=ships,
        fleet_speed=fleet_speed,
        technology=technology)
    fuel_consumption = engine.flight_fuel_consumption(
        distance=distance,
        ships=ships,
        flight_duration=flight_duration,
        holding_time=holding_time,
        technology=technology)
    return fuel_consumption


def get_cargo(resources: Dict[Resource, int],
              free_cargo_capacity: int) -> Dict[Resource, int]:
    """ Get resources that can be loaded on the ships. Priority descending: deuterium, crystal, metal. """
    loaded_resources = {}
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
                ships: Dict[Ship, int] = None,
                cargo: Dict[Resource, int] = None,
                arrival_time: int = None,
                arrives_before: int = None,
                arrives_after: int = None,
                departure_time: int = None,
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
            and (not ships or remove_empty_values(fleet.ships, empty=0) == remove_empty_values(ships, empty=0))
            and (not cargo or remove_empty_values(fleet.cargo, empty=0) == remove_empty_values(cargo, empty=0))
            and (not arrival_time or fleet.arrival_time == arrival_time)
            and (not arrives_before or fleet.arrival_time < arrives_before)
            and (not arrives_after or fleet.arrival_time > arrives_after)
            and (not departure_time or fleet.departure_time == departure_time)
            and (not departs_before or fleet.departure_time < departs_before)
            and (not departs_after or fleet.departure_time > departs_after)
            and (is_return_flight is None or fleet.return_flight == is_return_flight)]


def get_earliest_fleet_per_destination(
        fleets: Iterable[Union[FleetEvent, FleetMovement]]) -> List[Union[FleetEvent, FleetMovement]]:
    """ For each destination get the fleet that arrives first. """
    destinations = {}
    for fleet in fleets:
        prev_fleet = destinations.get(fleet.dest)
        if not prev_fleet or fleet.arrival_time < prev_fleet.arrival_time:
            destinations[fleet.dest] = fleet
    return list(destinations.values())


def get_earliest_fleet(
        fleets: Iterable[Union[FleetEvent, FleetMovement]]) -> Optional[Union[FleetEvent, FleetMovement]]:
    """ Get the fleet that is arriving first. """
    return min(fleets, key=lambda fleet: fleet.arrival_time, default=None)


def get_latest_fleet(fleets: Iterable[Union[FleetEvent, FleetMovement]]) -> Optional[Union[FleetEvent, FleetMovement]]:
    """ Get the fleet that is arriving last. """
    return max(fleets, key=lambda fleet: fleet.arrival_time, default=None)


def ships_exist(ships: Dict[Ship, int]) -> bool:
    """ Check whether there are any ships. """
    return any(ships.values())


def enough_ships(available_ships: Dict[Ship, int],
                 required_ships: Dict[Ship, int]) -> bool:
    """ Check whether there are enough ships. """
    return all(amount <= available_ships.get(ship, 0) for ship, amount in required_ships.items())


def remove_empty_values(dictionary, empty):
    return {k: v for k, v in dictionary.items() if v != empty}


def match_planet(coords: Coordinates, planets: List[Planet]) -> Planet:
    """ Find planet corresponding to the coordinates. """
    return next((planet for planet in planets if planet.coords == coords), None)


def format_fleet_events(events: List[FleetEvent], planets: List[Planet] = None) -> str:
    def format_event(event: FleetEvent):
        mission = f'{event.mission}{" (R)" if event.return_flight else ""}'
        direction = '<-' if event.return_flight else '->'
        return f'  {ftime(event.arrival_time)} | {mission:<16} | ' \
               f'{match_planet(event.origin, planets) or event.origin} {direction} ' \
               f'{match_planet(event.dest, planets) or event.dest}'

    events_string = '\n'.join(map(format_event, events))
    return events_string


def now(): return round(time.time())


def uuid4(): return uuid.uuid4().hex
