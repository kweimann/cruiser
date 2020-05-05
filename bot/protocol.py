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
class NotifyEscapeScheduled:
    planet: Planet  # escape scheduled on planet
    hostile_arrival: int  # hostile arrival on planet
    escape_time: int  # when to save fleet


@dataclasses.dataclass
class NotifyFleetEscaped:
    origin: Planet  # fleet escaped from origin
    hostile_arrival: int  # hostile arrival at origin
    destination: Planet = None  # fleet escaped to destination
    error: str = None


@dataclasses.dataclass
class NotifyFleetRecalled:
    origin: Planet  # fleet was sent from origin
    destination: Planet  # fleet was flying to destination
    hostile_arrival: int  # hostile arrival at destination
    error: str = None
