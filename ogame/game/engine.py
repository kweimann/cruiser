import logging
import math
from typing import Union, Dict, Tuple

from ogame.api.model import ServerData
from ogame.game.const import (
    Ship,
    Technology,
    CharacterClass
)
from ogame.game.data import (
    SHIP,
    DRIVE,
    EXPEDITION_BASE_LOOT,
    EXPEDITION_PATHFINDER_BONUS,
    EXPEDITION_MAX_FACTOR,
    GENERAL_FUEL_CONSUMPTION_FACTOR,
    MILITARY_SHIPS,
    DriveData
)
from ogame.game.model import (
    Coordinates,
    Planet
)


class Engine:
    def __init__(self,
                 server_data: ServerData,
                 character_class: CharacterClass = None):
        self.server_data = server_data
        self.character_class = character_class

    def distance(self,
                 a: Union[Coordinates, Planet],
                 b: Union[Coordinates, Planet]) -> int:
        """ Calculate the distance units between two coordinate systems. """
        if isinstance(a, Planet):
            a = a.coords
        if isinstance(b, Planet):
            b = b.coords
        if a.galaxy != b.galaxy:
            galaxy_diff = abs(a.galaxy - b.galaxy)
            if self.server_data.donut_galaxy:
                return 20000 * min(galaxy_diff, self.server_data.galaxies - galaxy_diff)
            else:
                return 20000 * galaxy_diff
        elif a.system != b.system:
            system_diff = abs(a.system - b.system)
            if self.server_data.donut_system:
                return 2700 + 95 * min(system_diff, self.server_data.systems - system_diff)
            else:
                return 2700 + 95 * system_diff
        elif a.position != b.position:
            position_diff = abs(a.position - b.position)
            return 1000 + 5 * position_diff
        elif a.type != b.type:
            return 5
        else:
            return 0

    def flight_duration(self,
                        distance: int,
                        ships: Dict[Ship, int],
                        fleet_speed: int = 10,
                        technology: Dict[Technology, int] = None) -> int:
        """
        @param distance: distance units between two coordinate systems
        @param ships: dictionary describing the size of the fleet
        @param fleet_speed: fleet speed (1-10)
        @param technology: dictionary describing the current technology levels
        @return: duration of the flight in seconds
        """
        if not any(ships.values()):
            raise ValueError('Cannot calculate flight duration if there are not ships.')
        lowest_ship_speed = min([self.ship_speed(ship, technology)
                                 for ship, amount in ships.items()
                                 if amount > 0])
        return self._flight_duration(
            distance=distance,
            ship_speed=lowest_ship_speed,
            speed_percentage=10 * fleet_speed)

    def fuel_consumption(self,
                         distance: int,
                         ships: Dict[Ship, int],
                         flight_duration: int,
                         holding_time: int = 0,
                         technology: Dict[Technology, int] = None) -> int:
        """
        @param distance: distance units between two coordinate systems
        @param ships: dictionary describing the size of the fleet
        @param flight_duration: duration of the flight in seconds
        @param holding_time: holding duration in hours
        @param technology: dictionary describing the current technology levels
        @return: fuel consumption of the entire fleet
        """
        if not any(ships.values()):
            raise ValueError('Cannot calculate fuel consumption if there are not ships.')
        deuterium_save_factor = self.server_data.global_deuterium_save_factor
        if self.character_class == CharacterClass.general:
            deuterium_save_factor = GENERAL_FUEL_CONSUMPTION_FACTOR * deuterium_save_factor
        total_fuel_consumption = 0
        for ship, amount in ships.items():
            if amount > 0:
                drive_technology, drive_data = self._get_drive(ship, technology)
                ship_speed_ = self.ship_speed(ship, technology)
                base_fuel_consumption = int(deuterium_save_factor * drive_data.fuel_consumption)
                ship_fuel_consumption = self._fuel_consumption(
                    base_fuel_consumption=base_fuel_consumption,
                    distance=distance,
                    ship_speed=ship_speed_,
                    flight_duration=flight_duration)
                total_fuel_consumption += ship_fuel_consumption * amount
                if holding_time:
                    ship_holding_consumption = holding_time * base_fuel_consumption / 10
                    total_fuel_consumption += ship_holding_consumption * amount
        return round(total_fuel_consumption) + 1

    def cargo_capacity(self,
                       ships: Dict[Ship, int],
                       technology: Dict[Technology, int] = None) -> int:
        """
        @param ships: dictionary describing the size of the fleet
        @param technology: dictionary describing the current technology levels
        @return: cargo capacity of the entire fleet
        """
        if not any(ships.values()):
            raise ValueError('Cannot calculate cargo capacity if there are not ships.')
        total_cargo_capacity_factor = 1
        total_cargo_capacity = 0
        if technology is not None:
            if Technology.hyperspace_technology not in technology:
                logging.warning(f'Missing {Technology.hyperspace_technology} in technology.')
            hyperspace_technology_level = technology.get(Technology.hyperspace_technology, 0)
            cargo_capacity_factor = self.server_data.cargo_hyperspace_tech_percentage / 100
            total_cargo_capacity_factor += hyperspace_technology_level * cargo_capacity_factor
        for ship, amount in ships.items():
            if amount > 0:
                if ship == Ship.espionage_probe:
                    ship_capacity = self.server_data.probe_cargo
                else:
                    ship_capacity = SHIP[ship].capacity
                class_cargo_capacity_factor = 0
                if self.character_class == CharacterClass.collector:
                    if ship == Ship.small_cargo or ship == Ship.large_cargo:
                        class_cargo_capacity_factor = \
                            self.server_data.miner_bonus_increased_cargo_capacity_for_trading_ships
                total_cargo_capacity += round(ship_capacity * amount *
                                              (total_cargo_capacity_factor + class_cargo_capacity_factor))
        return total_cargo_capacity

    def ship_speed(self,
                   ship: Ship,
                   technology: Dict[Technology, int] = None) -> int:
        """
        @param ship: ship
        @param technology: dictionary describing the current technology levels
        @return: actual speed of the ship
        """
        drive_technology, drive_data = Engine._get_drive(ship, technology)
        if drive_technology not in technology:
            logging.warning(f'Missing {drive_technology} in technology.')
        base_speed = drive_data.speed
        drive_level = technology.get(drive_technology, 0)
        drive_factor = DRIVE[drive_technology]
        drive_bonus = base_speed * drive_factor * drive_level
        class_bonus = 0
        if self.character_class == CharacterClass.general:
            if ship in MILITARY_SHIPS:
                class_bonus = int(base_speed * self.server_data.warrior_bonus_faster_combat_ships)
            elif ship == Ship.recycler:
                class_bonus = int(base_speed * self.server_data.warrior_bonus_faster_recyclers)
        elif self.character_class == CharacterClass.collector:
            if ship == Ship.small_cargo or ship == ship.large_cargo:
                class_bonus = int(base_speed * self.server_data.miner_bonus_faster_trading_ships)
        return base_speed + drive_bonus + class_bonus

    def max_expedition_find(self,
                            ships: Dict[Ship, int] = None,
                            pathfinder_in_fleet: bool = None) -> int:
        """
        @param ships: dictionary describing the size of the fleet
        @param pathfinder_in_fleet: whether a pathfinder is in the fleet
        @return: maximal possible expedition find (metal)
        """
        if ships:
            expedition_points = self.expedition_points(ships)
            if pathfinder_in_fleet is None:
                pathfinder_in_fleet = ships.get(Ship.pathfinder, 0) > 0
        else:
            expedition_points = self.max_expedition_points
            pathfinder_in_fleet = pathfinder_in_fleet or False
        return self._expedition_find(
            expedition_points=expedition_points,
            expedition_factor=EXPEDITION_MAX_FACTOR,
            pathfinder_in_fleet=pathfinder_in_fleet)

    def expedition_points(self, ships: Union[Ship, Dict[Ship, int]]) -> int:
        """
        @param ships: dictionary describing the size of the fleet or a single ship
        @return: number of expedition points of the fleet
        """
        if isinstance(ships, Ship):
            ships = {ships: 1}
        total_structural_integrity = 0
        for ship, amount in ships.items():
            total_structural_integrity += amount * SHIP[ship].structural_integrity
        return min(5 * total_structural_integrity // 1000, self.max_expedition_points)

    @property
    def max_expedition_points(self) -> int:
        """ Get maximum possible expedition point in the universe. """
        if self.server_data.top_score < 1e5:
            return 2500
        elif self.server_data.top_score < 1e6:
            return 6000
        elif self.server_data.top_score < 5e6:
            return 9000
        elif self.server_data.top_score < 25e6:
            return 12000
        elif self.server_data.top_score < 50e6:
            return 15000
        elif self.server_data.top_score < 75e6:
            return 18000
        elif self.server_data.top_score < 1e8:
            return 21000
        else:
            return 25000

    def _expedition_find(self,
                         expedition_points: int,
                         expedition_factor: int,
                         pathfinder_in_fleet: bool = False) -> int:
        """
        @param expedition_points: number of expedition points
        @param pathfinder_in_fleet: whether a pathfinder is in the fleet
        @return: maximal expedition find (metal) given the expedition points and current top 1 score
        """
        expedition_points = min(expedition_points, self.max_expedition_points)
        loot_boost = self._expedition_loot_boost(pathfinder_in_fleet=pathfinder_in_fleet)
        return int(loot_boost * expedition_points * expedition_factor)

    def _expedition_loot_boost(self, pathfinder_in_fleet: bool = False) -> float:
        """
        @param pathfinder_in_fleet: whether a pathfinder is in the fleet
        @return: expedition loot boost
        """
        class_bonus = 0
        if self.server_data.character_classes_enabled and self.character_class == CharacterClass.discoverer:
            class_bonus = self.server_data.explorer_bonus_increased_expedition_outcome
        loot_boost = (EXPEDITION_BASE_LOOT + class_bonus) * self.server_data.speed
        if pathfinder_in_fleet:
            loot_boost = EXPEDITION_PATHFINDER_BONUS * loot_boost
        return loot_boost

    @staticmethod
    def _get_drive(ship: Ship,
                   technology: Dict[Technology, int] = None) -> Tuple[Technology, DriveData]:
        """
        @param ship: ship
        @param technology: dictionary describing the current technology levels
        @return: tuple describing the drive
        """

        def get_speed_multiplier(drive_key_value):
            return DRIVE[drive_key_value[0]]

        ship_data = SHIP[ship]
        # find the best available drive
        if technology is not None:
            available_drives = {
                drive_technology: drive_data for drive_technology, drive_data in ship_data.drives.items()
                if technology.get(drive_technology, 0) >= drive_data.min_level}
            if available_drives:
                return max(available_drives.items(), key=get_speed_multiplier)
        # otherwise return the default drive (slowest of all)
        return min(ship_data.drives.items(), key=get_speed_multiplier)

    def _fuel_consumption(self,
                          base_fuel_consumption: float,
                          distance: int,
                          ship_speed: int,
                          flight_duration: int) -> float:
        """
        @param base_fuel_consumption: base fuel consumption of the ship
        @param distance: distance units between two coordinate systems
        @param ship_speed: ship speed
        @param flight_duration duration of the flight in seconds
        @return: fuel consumption of the ship
        """
        return base_fuel_consumption * distance / 35000 * (
                35000 / (flight_duration * self.server_data.fleet_speed - 10)
                * math.sqrt(10 * distance / ship_speed) / 10 + 1) ** 2

    def _flight_duration(self,
                         distance: int,
                         ship_speed: int,
                         speed_percentage: int = 100) -> int:
        """
        @param distance: distance units between two coordinate systems
        @param ship_speed: ship speed
        @param speed_percentage: speed percentage
        @return: duration of the flight in seconds
        """
        return round((35000 / speed_percentage *
                      math.sqrt(distance * 1000 / ship_speed) + 10) / self.server_data.fleet_speed)
