import math
from ogame.game.ships import SHIPS
from ogame.game.technology import TECHNOLOGY


def distance(origin_coords, dest_coords):
    """
    :param origin_coords: (galaxy, system, position)
    :param dest_coords: (galaxy, system, position)
    :return: distance units between two coordinate systems
    """
    origin_galaxy, origin_system, origin_position = origin_coords
    dest_galaxy, dest_system, dest_position = dest_coords

    if origin_galaxy != dest_galaxy:
        return 20000 * abs(origin_galaxy - dest_galaxy)
    elif origin_system != dest_system:
        return 2700 + 95 * abs(origin_system - dest_system)
    elif origin_position != dest_position:
        return 1000 + 5 * abs(origin_position - dest_position)
    else:
        return 5


def flight_duration(distance,
                    ships,
                    speed_percentage=100,
                    universe_fleet_speed_modifier=1,
                    technology=None):
    """
    :param distance: distance units between two coordinate systems
    :param ships: dictionary of {ship: ship_count}
    :param speed_percentage: percentage of ship's speed
    :param universe_fleet_speed_modifier: universe fleet speed
    :param technology: dictionary of { technology: level }
    :return: duration of the flight in seconds
    """
    ship_speeds = [
        ship_speed(ship, technology) for ship, ship_count in ships.items() if ship_count > 0
    ]

    return _flight_duration(distance=distance,
                            ship_speed=min(ship_speeds),
                            speed_percentage=speed_percentage,
                            universe_fleet_speed_modifier=universe_fleet_speed_modifier)


def fuel_consumption(distance,
                     ships,
                     speed_percentage=100,
                     universe_fleet_speed_modifier=1,
                     universe_fuel_consumption_modifier=1,
                     technology=None):
    """
    :param distance: distance units between two coordinate systems
    :param ships: dictionary of {ship: ship_count}
    :param speed_percentage: percentage of fleet's speed
    :param universe_fleet_speed_modifier: universe fleet speed
    :param universe_fuel_consumption_modifier: fuel consumption multiplier
    :param technology: dictionary of { technology: level }
    :return: fuel consumption of whole fleet
    """
    total_fuel_consumption = 0

    flight_duration_ = flight_duration(distance=distance,
                                       ships=ships,
                                       speed_percentage=speed_percentage,
                                       universe_fleet_speed_modifier=universe_fleet_speed_modifier,
                                       technology=technology)

    for ship, ship_count in ships.items():
        if ship_count > 0:
            drive_params = _get_drive(ship, technology)
            ship_speed_ = ship_speed(ship, technology)
            base_fuel_consumption = universe_fuel_consumption_modifier * drive_params['base_fuel_consumption']
            ship_fuel_consumption = _fuel_consumption(base_fuel_consumption=base_fuel_consumption,
                                                      distance=distance,
                                                      ship_speed=ship_speed_,
                                                      flight_duration=flight_duration_,
                                                      universe_fleet_speed_modifier=universe_fleet_speed_modifier)
            total_fuel_consumption += ship_count * ship_fuel_consumption

    return round(total_fuel_consumption) + 1


def cargo_capacity(ships, technology=None):
    """
    :param ships: dictionary of {ship: ship_count}
    :param technology: dictionary of { technology: level }
    :return: cargo capacity of whole fleet
    """
    total_cargo_capacity_multiplier = 1
    total_cargo_capacity = 0

    if technology:
        hyperspace_technology_level = technology.get('hyperspace_technology', 0)
        cargo_capacity_multiplier = TECHNOLOGY['hyperspace_technology']['cargo_capacity_multiplier']
        total_cargo_capacity_multiplier += hyperspace_technology_level * cargo_capacity_multiplier

    for ship, ship_count in ships.items():
        if ship_count > 0:
            cargo_capacity_ = SHIPS[ship]['cargo_capacity']
            total_cargo_capacity += round(total_cargo_capacity_multiplier * ship_count * cargo_capacity_)

    return total_cargo_capacity


def ship_speed(ship, technology=None):
    """
    :param ship: ship key
    :param technology: dictionary of { technology: level }
    :return: actual speed of the ship
    """
    drive_params = _get_drive(ship, technology)
    base_speed = drive_params['base_speed']
    drive_level = drive_params['level']
    drive_multiplier = TECHNOLOGY[drive_params['name']]['speed_multiplier']
    return _ship_speed(base_speed=base_speed,
                       drive_level=drive_level,
                       drive_multiplier=drive_multiplier)


def _get_drive(ship, technology=None):
    """
    :param ship: ship key
    :param technology: dictionary of { technology: level }
    :return: updated drive params dictionary
    {
        name: str,
        level: int,
        min_level: int,
        base_speed: int,
        base_fuel_consumption: int,
    }
    """
    # sort available drives by their multiplier in descending order (best first)
    sorted_drives = sorted(SHIPS[ship]['drives'].items(),
                           key=lambda kv: TECHNOLOGY[kv[0]]['speed_multiplier'],
                           reverse=True)

    if technology:
        # check if ship's drive has been updated
        for drive, drive_params in sorted_drives:
            if drive in technology and technology[drive] >= drive_params['min_level']:
                updated_drive_params = dict(name=drive,
                                            level=technology[drive],
                                            **drive_params)
                return updated_drive_params

    # return default drive
    drive, drive_params = sorted_drives[-1]
    updated_drive_params = dict(name=drive,
                                level=drive_params['min_level'],
                                **drive_params)

    return updated_drive_params


def _ship_speed(base_speed, drive_level, drive_multiplier):
    """
    :param base_speed: base speed of a ship
    :param drive_level: drive level
    :param drive_multiplier: drive bonus factor
    :return: actual ship's speed
    """
    return int(base_speed * (1 + drive_level * drive_multiplier))


def _fuel_consumption(base_fuel_consumption,
                      distance,
                      ship_speed,
                      flight_duration,
                      universe_fleet_speed_modifier=1):
    """
    :param base_fuel_consumption: base fuel consumption of the ship
    :param distance: distance units between two coordinate systems
    :param ship_speed: speed of the ship
    :param flight_duration duration of the flight in seconds
    :param universe_fleet_speed_modifier: universe fleet speed
    :return: fuel consumption of the ship
    """
    return base_fuel_consumption * distance / 35000 * (
            35000 / (flight_duration * universe_fleet_speed_modifier - 10)
            * math.sqrt(10 * distance / ship_speed) / 10 + 1) ** 2


def _flight_duration(distance,
                     ship_speed,
                     speed_percentage=100,
                     universe_fleet_speed_modifier=1):
    """
    :param distance: distance units between two coordinate systems
    :param ship_speed: speed of the ship
    :param speed_percentage: percentage of ship's speed
    :param universe_fleet_speed_modifier: universe fleet speed
    :return: duration of the flight in seconds
    """
    return round((35000 / speed_percentage *
                 math.sqrt(distance * 1000 / ship_speed) + 10) / universe_fleet_speed_modifier)
