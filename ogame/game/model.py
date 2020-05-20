import dataclasses
from typing import Dict, Union, List

from ogame.game.const import (
    Mission,
    CoordsType,
    Ship,
    Technology,
    Resource,
    CharacterClass
)


@dataclasses.dataclass(order=True, frozen=True)
class Coordinates:
    galaxy: int
    system: int
    position: int
    type: CoordsType
    def __str__(self): return f'[{self.type.name.capitalize()[0]}:{self.galaxy}:{self.system}:{self.position}]'
    def __repr__(self): return f'[{self.type.name.capitalize()[0]}:{self.galaxy}:{self.system}:{self.position}]'


@dataclasses.dataclass(frozen=True)
class Planet:
    id: int
    name: str
    coords: Coordinates
    def __str__(self): return f'{self.name} {self.coords}'
    def __repr__(self): return f'{self.name} {self.coords}'


@dataclasses.dataclass(frozen=True)
class FleetEvent:
    id: int
    origin: Coordinates
    dest: Coordinates
    arrival_time: int
    mission: Mission
    return_flight: bool
    player_id: int = None


@dataclasses.dataclass(frozen=True)
class Production:
    o: Union[Ship, Technology]
    start: int
    end: int
    amount: int = 1


@dataclasses.dataclass(frozen=True)
class Overview:
    planets: List[Planet]
    character_class: CharacterClass = None


@dataclasses.dataclass(frozen=True)
class Shipyard:
    ships: Dict[Ship, int]
    production: Production = None


@dataclasses.dataclass(frozen=True)
class Research:
    technology: Dict[Technology, int]
    production: Production = None


@dataclasses.dataclass(frozen=True)
class Resources:
    amount: Dict[Resource, int]
    storage: Dict[Resource, int]


@dataclasses.dataclass(frozen=True)
class FleetMovement:
    id: int
    origin: Coordinates
    dest: Coordinates
    departure_time: int
    arrival_time: int
    mission: Mission
    return_flight: bool
    ships: Dict[Ship, int]
    cargo: Dict[Resource, int]
    holding: bool = False
    holding_time: int = 0

    @property
    def flight_duration(self) -> int:
        if self.holding:
            return self.arrival_time - self.departure_time - self.holding_time
        else:
            return (self.arrival_time - self.departure_time - self.holding_time) // 2

    @property
    def holding_start(self) -> int:
        if self.holding:
            return self.departure_time
        elif self.holding_time:
            # fleet is on its way to hold
            return self.departure_time + self.flight_duration

    @property
    def holding_end(self) -> int:
        if self.holding_time:
            return self.arrival_time - self.flight_duration


@dataclasses.dataclass(frozen=True)
class Movement:
    fleets: List[FleetMovement]
    used_fleet_slots: int
    max_fleet_slots: int
    used_expedition_slots: int
    max_expedition_slots: int
    timestamp: int

    @property
    def free_fleet_slots(self) -> int: return self.max_fleet_slots - self.used_fleet_slots

    @property
    def free_expedition_slots(self) -> int: return self.max_expedition_slots - self.used_expedition_slots


@dataclasses.dataclass(frozen=True)
class FleetDispatch:
    dispatch_token: str
    ships: Dict[Ship, int]
    used_fleet_slots: int
    max_fleet_slots: int
    used_expedition_slots: int
    max_expedition_slots: int
    timestamp: int

    @property
    def free_fleet_slots(self) -> int: return self.max_fleet_slots - self.used_fleet_slots

    @property
    def free_expedition_slots(self) -> int: return self.max_expedition_slots - self.used_expedition_slots
