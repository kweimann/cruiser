import dataclasses
from typing import Dict, Union

from ogame.game.const import Ship
from ogame.game.model import Coordinates, Planet


@dataclasses.dataclass
class WakeUp:
    id: str = None


@dataclasses.dataclass
class SendExpedition:
    id: str
    origin: Coordinates
    dest: Coordinates
    ships: Dict[Ship, int]
    holding_time: int = 1
    repeat: Union[int, str] = 'forever'


@dataclasses.dataclass
class CancelExpedition:
    id: str
    return_fleet: bool = False


# Log messages


@dataclasses.dataclass
class NotifyWakeUp:
    pass


@dataclasses.dataclass
class NotifyHostileEvent:
    planet: Planet  # planet under attack
    hostile_arrival: int  # time of hostile arrival
    previous_hostile_arrival: int = None  # previous time of hostile arrival (flight was delayed)


@dataclasses.dataclass
class NotifyHostileEventRecalled:
    planet: Planet
    hostile_arrival: int


@dataclasses.dataclass
class NotifyPlanetsSafe:
    pass


@dataclasses.dataclass
class NotifyFleetSaved:
    origin: Planet  # saved planet
    hostile_arrival: int  # time of hostile arrival
    destination: Planet = None  # destination the fleet escaped to
    error: str = None


@dataclasses.dataclass
class NotifyFleetRecalled:
    origin: Planet  # fleet was sent from origin
    destination: Planet  # fleet was flying to destination
    hostile_arrival: int  # hostile arrival at destination
    error: str = None


@dataclasses.dataclass
class NotifySavedFleetRecalled:
    origin: Planet  # fleet flying back to origin
    error: str = None


@dataclasses.dataclass
class NotifyExpeditionFinished:
    expedition: SendExpedition
    error: str = None


@dataclasses.dataclass
class NotifyExpeditionCancelled:
    expedition: SendExpedition
    cancellation: CancelExpedition
    fleet_returned: bool
