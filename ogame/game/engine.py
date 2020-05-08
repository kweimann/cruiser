import logging
import math
from typing import Union, Dict

from ogame.api.model import ServerData
from ogame.game.const import (
    Ship,
    Technology,
    CharacterClass,
    Resource
)
from ogame.game.data import (
    SHIP_DATA,
    DRIVE_FACTOR,
    EXPEDITION_BASE_LOOT,
    EXPEDITION_PATHFINDER_BONUS,
    EXPEDITION_MAX_FACTOR,
    GENERAL_FUEL_CONSUMPTION_FACTOR
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
        flight_fuel_consumption = 0
        holding_fuel_consumption = 0
        for ship, amount in ships.items():
            if amount > 0:
                ship_speed_ = self.ship_speed(ship, technology)
                drive_technology = self._drive_technology(ship, technology)
                drive_fuel_consumption = SHIP_DATA[ship].drives[drive_technology].fuel_consumption
                base_fuel_consumption = int(self._deuterium_save_factor * drive_fuel_consumption)
                ship_fuel_consumption = self._flight_fuel_consumption(
                    base_fuel_consumption=base_fuel_consumption,
                    distance=distance,
                    ship_speed=ship_speed_,
                    flight_duration=flight_duration)
                ship_holding_consumption = self._holding_fuel_consumption(
                    base_fuel_consumption=base_fuel_consumption,
                    holding_time=holding_time)
                flight_fuel_consumption += amount * ship_fuel_consumption
                holding_fuel_consumption += amount * ship_holding_consumption
        flight_fuel_consumption = round(flight_fuel_consumption) + 1
        holding_fuel_consumption = round(holding_fuel_consumption) + 1
        total_fuel_consumption = flight_fuel_consumption + holding_fuel_consumption
        return total_fuel_consumption

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
        hyperspace_technology_level = None
        if technology:
            hyperspace_technology_level = technology.get(Technology.hyperspace_technology)
            if hyperspace_technology_level is None:
                logging.warning(f'Missing {Technology.hyperspace_technology} in technology.')
        total_capacity = 0
        for ship, amount in ships.items():
            if amount > 0:
                ship_capacity = self._ship_capacity(
                    ship=ship,
                    hst_level=hyperspace_technology_level)
                total_capacity += amount * ship_capacity
        return total_capacity

    def ship_speed(self,
                   ship: Ship,
                   technology: Dict[Technology, int] = None) -> int:
        """
        @param ship: ship
        @param technology: dictionary describing the current technology levels
        @return: actual speed of the ship
        """
        drive_technology = self._drive_technology(ship, technology)
        drive_technology_level = None
        if technology:
            drive_technology_level = technology.get(drive_technology)
            if drive_technology_level is None:
                logging.warning(f'Missing {drive_technology} in technology.')
        base_speed = SHIP_DATA[ship].drives[drive_technology].speed
        drive_bonus = self._drive_bonus_ship_speed(
            ship=ship,
            drive_technology=drive_technology,
            drive_level=drive_technology_level)
        class_bonus = self._class_bonus_ship_speed(
            ship=ship,
            drive_technology=drive_technology)
        speed = base_speed + drive_bonus + class_bonus
        return speed

    def max_expedition_find(self,
                            ships: Dict[Ship, int] = None,
                            resource: Resource = Resource.metal,
                            pathfinder_in_fleet: bool = None) -> int:
        """
        @param ships: dictionary describing the size of the fleet
        @param resource: type of find
        @param pathfinder_in_fleet: whether a pathfinder is in the fleet
        @return: maximal possible expedition find
        """
        if ships:
            expedition_points = self.expedition_points(ships)
            if pathfinder_in_fleet is None:
                pathfinder_in_fleet = ships.get(Ship.pathfinder, 0) > 0
        else:
            expedition_points = self.max_expedition_points
            pathfinder_in_fleet = pathfinder_in_fleet or False
        max_find = self._expedition_find(
            expedition_points=expedition_points,
            expedition_factor=EXPEDITION_MAX_FACTOR,
            pathfinder_in_fleet=pathfinder_in_fleet)
        if resource == Resource.metal:
            return max_find
        elif resource == Resource.crystal:
            return max_find // 2
        elif resource == Resource.deuterium:
            return max_find // 3
        elif resource == Resource.dark_matter:
            return 1800
        else:
            raise ValueError(f'resource cannot be found: {resource}')

    def expedition_points(self, ships: Union[Ship, Dict[Ship, int]]) -> int:
        """
        @param ships: dictionary describing the size of the fleet or a single ship
        @return: number of expedition points of the fleet
        """
        if isinstance(ships, Ship):
            ships = {ships: 1}
        total_structural_integrity = 0
        for ship, amount in ships.items():
            total_structural_integrity += amount * SHIP_DATA[ship].structural_integrity
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
    def _drive_bonus_ship_speed(ship: Ship,
                                drive_technology: Technology,
                                drive_level: int = None) -> int:
        """
        @param ship: ship
        @param drive_technology: drive technology of the ship
        @param drive_level: drive technology level
        @return: bonus ship speed from drive level
        """
        base_speed = SHIP_DATA[ship].drives[drive_technology].speed
        drive_factor = DRIVE_FACTOR[drive_technology]
        drive_level = drive_level or 0
        drive_bonus = base_speed * drive_factor * drive_level
        return drive_bonus

    def _class_bonus_ship_speed(self,
                                ship: Ship,
                                drive_technology: Technology) -> int:
        """
        @param ship: ship
        @param drive_technology: drive technology of the ship
        @return: bonus ship speed from the character class
        """
        class_bonus = 0
        base_speed = SHIP_DATA[ship].drives[drive_technology].speed
        if self.character_class == CharacterClass.general:
            if SHIP_DATA[ship].is_military:
                class_bonus = int(base_speed * self.server_data.warrior_bonus_faster_combat_ships)
            elif ship == Ship.recycler:
                class_bonus = int(base_speed * self.server_data.warrior_bonus_faster_recyclers)
        elif self.character_class == CharacterClass.collector:
            if ship == Ship.small_cargo or ship == ship.large_cargo:
                class_bonus = int(base_speed * self.server_data.miner_bonus_faster_trading_ships)
        return class_bonus

    @staticmethod
    def _drive_technology(ship: Ship,
                          technology: Dict[Technology, int] = None) -> Technology:
        """
        @param ship: ship
        @param technology: dictionary describing the current technology levels
        @return: currently used drive technology
        """
        # find the best available drive
        if technology:
            available_drives = [drive_technology for drive_technology, drive_data in SHIP_DATA[ship].drives.items()
                                if technology.get(drive_technology, 0) >= drive_data.min_level]
            if available_drives:
                return max(available_drives, key=DRIVE_FACTOR.get)
        # otherwise return the default drive (slowest of all)
        return min(SHIP_DATA[ship].drives, key=DRIVE_FACTOR.get)

    def _flight_fuel_consumption(self,
                                 base_fuel_consumption: int,
                                 distance: int,
                                 ship_speed: int,
                                 flight_duration: int) -> float:
        """
        @param base_fuel_consumption: base fuel consumption of a ship
        @param distance: distance units between two coordinate systems
        @param ship_speed: ship speed
        @param flight_duration duration of the flight in seconds
        @return: fuel consumption of a ship for the flight
        """
        return base_fuel_consumption * distance / 35000 * (
                35000 / (flight_duration * self.server_data.fleet_speed - 10)
                * math.sqrt(10 * distance / ship_speed) / 10 + 1) ** 2

    @staticmethod
    def _holding_fuel_consumption(base_fuel_consumption: int,
                                  holding_time: int = 1) -> float:
        """
        @param base_fuel_consumption: base fuel consumption of a ship
        @param holding_time: holding duration in hours
        @return: fuel consumption of a ship for the holding duration
        """
        return holding_time * base_fuel_consumption / 10

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

    def _ship_capacity(self,
                       ship: Ship,
                       hst_level: int = None) -> int:
        """
        @param ship: ship
        @param hst_level: hyperspace technology level
        @return: total capacity of a ship
        """
        if ship == Ship.espionage_probe:
            base_capacity = self.server_data.probe_cargo
        else:
            base_capacity = SHIP_DATA[ship].capacity
        hst_bonus = self._hst_bonus_capacity(
            ship=ship,
            hst_level=hst_level)
        class_bonus = self._class_bonus_capacity(ship=ship)
        total_capacity = base_capacity + hst_bonus + class_bonus
        return total_capacity

    def _class_bonus_capacity(self, ship: Ship) -> int:
        """
        @param ship: ship
        @return: bonus capacity from character class
        """
        base_capacity = SHIP_DATA[ship].capacity
        class_bonus = 0
        if self.character_class == CharacterClass.collector:
            if ship == Ship.small_cargo or ship == Ship.large_cargo:
                capacity_factor = self.server_data.miner_bonus_increased_cargo_capacity_for_trading_ships
                class_bonus = int(base_capacity * capacity_factor)
        return class_bonus

    def _hst_bonus_capacity(self,
                            ship: Ship,
                            hst_level: int = None) -> int:
        """
        @param ship: ship
        @param hst_level: hyperspace technology level
        @return: bonus capacity from hyperspace technology
        """
        base_capacity = SHIP_DATA[ship].capacity
        hst_level = hst_level or 0
        hst_factor = self.server_data.cargo_hyperspace_tech_percentage / 100
        hst_bonus = int(base_capacity * hst_factor) * hst_level
        return hst_bonus

    @property
    def _deuterium_save_factor(self) -> float:
        save_factor = self.server_data.global_deuterium_save_factor
        if self.character_class == CharacterClass.general:
            save_factor = GENERAL_FUEL_CONSUMPTION_FACTOR * save_factor
        return save_factor
