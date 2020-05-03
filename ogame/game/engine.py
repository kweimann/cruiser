import logging
import math
from typing import Union, Dict

from ogame.api.model import ServerData
from ogame.game.const import (
    Ship,
    Technology
)
from ogame.game.data import SHIP, TECHNOLOGY
from ogame.game.model import (
    Coordinates,
    Planet
)


class Engine:
    def __init__(self, server_data: ServerData):
        self.server_data = server_data

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
                        fleet_speed: int = 100,
                        technology: Dict[Technology, int] = None) -> int:
        """
        :param distance: distance units between two coordinate systems
        :param ships: dictionary describing the size of the fleet
        :param fleet_speed: fleet speed
        :param technology: dictionary describing the current technology levels
        :return: duration of the flight in seconds
        """
        lowest_ship_speed = min([self.ship_speed(ship, technology) for ship, amount in ships.items() if amount > 0])
        return self._flight_duration(distance=distance,
                                     ship_speed=lowest_ship_speed,
                                     fleet_speed=fleet_speed)

    def fuel_consumption(self,
                         distance: int,
                         ships: Dict[Ship, int],
                         flight_duration: int,
                         technology: Dict[Technology, int] = None) -> int:
        """
        :param distance: distance units between two coordinate systems
        :param ships: dictionary describing the size of the fleet
        :param flight_duration: duration of the flight in seconds
        :param technology: dictionary describing the current technology levels
        :return: fuel consumption of the entire fleet
        """
        total_fuel_consumption = 0
        for ship, amount in ships.items():
            if amount > 0:
                drive_params = self._get_drive(ship, technology)
                ship_speed_ = self.ship_speed(ship, technology)
                deuterium_save_factor = self.server_data.global_deuterium_save_factor
                base_fuel_consumption = deuterium_save_factor * drive_params['base_fuel_consumption']
                ship_fuel_consumption = self._fuel_consumption(base_fuel_consumption=base_fuel_consumption,
                                                               distance=distance,
                                                               ship_speed=ship_speed_,
                                                               flight_duration=flight_duration)
                total_fuel_consumption += ship_fuel_consumption * amount
        return round(total_fuel_consumption) + 1

    def cargo_capacity(self,
                       ships: Dict[Ship, int],
                       technology: Dict[Technology, int] = None) -> int:
        """
        :param ships: dictionary describing the size of the fleet
        :param technology: dictionary describing the current technology levels
        :return: cargo capacity of the entire fleet
        """
        total_cargo_capacity_factor = 1
        total_cargo_capacity = 0
        if technology is not None:
            if Technology.hyperspace_technology not in technology:
                logging.warning(f'Missing {Technology.hyperspace_technology} in technology.')
            hyperspace_technology_level = technology.get(Technology.hyperspace_technology, 0)
            cargo_capacity_factor = self.server_data.cargo_hyperspace_tech_percentage / 100
            total_cargo_capacity_factor = 1 + hyperspace_technology_level * cargo_capacity_factor
        for ship, amount in ships.items():
            if amount > 0:
                ship_capacity = SHIP[ship]['cargo_capacity']
                total_cargo_capacity += round(ship_capacity * amount * total_cargo_capacity_factor)
        return total_cargo_capacity

    @staticmethod
    def ship_speed(ship: Ship,
                   technology: Dict[Technology, int] = None) -> int:
        """
        :param ship: ship
        :param technology: dictionary describing the current technology levels
        :return: actual speed of the ship
        """
        drive_params = Engine._get_drive(ship, technology)
        base_speed = drive_params['base_speed']
        drive_level = drive_params['level']
        drive_factor = TECHNOLOGY[drive_params['drive']]['speed_multiplier']
        return Engine._ship_speed(base_speed=base_speed,
                                  drive_level=drive_level,
                                  drive_factor=drive_factor)

    @staticmethod
    def _get_drive(ship: Ship,
                   technology: Dict[Technology, int] = None):
        """
        :param ship: ship
        :param technology: dictionary describing the current technology levels
        :return: updated drive params dictionary
        {
            drive: Technology,
            level: int,
            min_level: int,
            base_speed: int,
            base_fuel_consumption: int,
        }
        """
        # sort available drives by their multiplier in descending order (best first)
        sorted_drives = sorted(SHIP[ship]['drives'].items(),
                               key=lambda kv: TECHNOLOGY[kv[0]]['speed_multiplier'],
                               reverse=True)
        if technology is not None:
            # check if ship's drive has been updated
            for drive, drive_params in sorted_drives:
                if drive not in technology:
                    logging.warning(f'Missing {drive} in technology.')
                drive_level = technology.get(drive, drive_params['min_level'])
                if drive_level >= drive_params['min_level']:
                    updated_drive_params = dict(drive=drive,
                                                level=drive_level,
                                                **drive_params)
                    return updated_drive_params
        # return default drive
        drive, drive_params = sorted_drives[-1]
        updated_drive_params = dict(drive=drive,
                                    level=drive_params['min_level'],
                                    **drive_params)
        return updated_drive_params

    @staticmethod
    def _ship_speed(base_speed: int,
                    drive_level: int,
                    drive_factor: float) -> int:
        """
        :param base_speed: base speed of a ship
        :param drive_level: drive level
        :param drive_factor: drive bonus factor
        :return: actual ship's speed
        """
        return int(base_speed * (1 + drive_level * drive_factor))

    def _fuel_consumption(self,
                          base_fuel_consumption: int,
                          distance: int,
                          ship_speed: int,
                          flight_duration: int) -> float:
        """
        :param base_fuel_consumption: base fuel consumption of the ship
        :param distance: distance units between two coordinate systems
        :param ship_speed: ship speed
        :param flight_duration duration of the flight in seconds
        :return: fuel consumption of the ship
        """
        return base_fuel_consumption * distance / 35000 * (
                35000 / (flight_duration * self.server_data.fleet_speed - 10)
                * math.sqrt(10 * distance / ship_speed) / 10 + 1) ** 2

    def _flight_duration(self,
                         distance: int,
                         ship_speed: int,
                         fleet_speed: int = 100) -> int:
        """
        :param distance: distance units between two coordinate systems
        :param ship_speed: ship speed
        :param fleet_speed: fleet speed
        :return: duration of the flight in seconds
        """
        return round((35000 / fleet_speed *
                      math.sqrt(distance * 1000 / ship_speed) + 10) / self.server_data.fleet_speed)
