import dataclasses
from typing import Dict, Union

from ogame.game.const import (
    Ship,
    Resource,
    Technology,
    Facility
)


@dataclasses.dataclass
class DriveData:
    speed: int
    fuel_consumption: int
    min_level: int


@dataclasses.dataclass
class ShipData:
    cost: Dict[Resource, int]
    requirements: Dict[Union[Technology, Facility], int]
    drives: Dict[Technology, DriveData]
    shield_power: int
    weapon_power: int
    capacity: int

    @property
    def structural_integrity(self):
        metal_cost = self.cost.get(Resource.metal, 0)
        crystal_cost = self.cost.get(Resource.crystal, 0)
        structural_integrity = metal_cost + crystal_cost
        return structural_integrity


EXPEDITION_BASE_LOOT = 1
EXPEDITION_PATHFINDER_BONUS = 2
EXPEDITION_MAX_FACTOR = 200

GENERAL_FUEL_CONSUMPTION_FACTOR = 0.75


DRIVE = {Technology.combustion_drive: 0.1,
         Technology.impulse_drive: 0.2,
         Technology.hyperspace_drive: 0.3}


MILITARY_SHIPS = [
    Ship.light_fighter,
    Ship.heavy_fighter,
    Ship.cruiser,
    Ship.battleship,
    Ship.battlecruiser,
    Ship.bomber,
    Ship.destroyer,
    Ship.deathstar,
    Ship.reaper,
    Ship.pathfinder
]

SHIP = {
    Ship.small_cargo:
        ShipData(
            cost={Resource.metal: 2000,
                  Resource.crystal: 2000},
            requirements={Technology.combustion_drive: 2,
                          Facility.shipyard: 2},
            drives={
                Technology.combustion_drive: DriveData(
                    speed=5000,
                    fuel_consumption=10,
                    min_level=2),
                Technology.impulse_drive: DriveData(
                    speed=10000,
                    fuel_consumption=20,
                    min_level=5)},
            shield_power=10,
            weapon_power=5,
            capacity=5000),

    Ship.large_cargo:
        ShipData(
            cost={Resource.metal: 6000,
                  Resource.crystal: 6000},
            requirements={Technology.combustion_drive: 6,
                          Facility.shipyard: 4},
            drives={
                Technology.combustion_drive: DriveData(
                    speed=7500,
                    fuel_consumption=50,
                    min_level=6)},
            shield_power=25,
            weapon_power=5,
            capacity=25000),

    Ship.light_fighter:
        ShipData(
            cost={Resource.metal: 3000,
                  Resource.crystal: 1000},
            requirements={Technology.combustion_drive: 1,
                          Facility.shipyard: 1},
            drives={
                Technology.combustion_drive: DriveData(
                    speed=12500,
                    fuel_consumption=20,
                    min_level=1)},
            shield_power=10,
            weapon_power=50,
            capacity=50),

    Ship.heavy_fighter:
        ShipData(
            cost={Resource.metal: 6000,
                  Resource.crystal: 4000},
            requirements={Technology.impulse_drive: 2,
                          Technology.armour_technology: 2,
                          Facility.shipyard: 3},
            drives={
                Technology.impulse_drive: DriveData(
                    speed=10000,
                    fuel_consumption=75,
                    min_level=2)},
            shield_power=25,
            weapon_power=150,
            capacity=100),

    Ship.cruiser:
        ShipData(
            cost={Resource.metal: 20000,
                  Resource.crystal: 7000,
                  Resource.deuterium: 2000},
            requirements={Technology.impulse_drive: 4,
                          Technology.ion_technology: 2,
                          Facility.shipyard: 5},
            drives={
                Technology.impulse_drive: DriveData(
                    speed=15000,
                    fuel_consumption=300,
                    min_level=4)},
            shield_power=50,
            weapon_power=400,
            capacity=800),

    Ship.battleship:
        ShipData(
            cost={Resource.metal: 45000,
                  Resource.crystal: 15000},
            requirements={Technology.hyperspace_drive: 4,
                          Facility.shipyard: 7},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=10000,
                    fuel_consumption=500,
                    min_level=4)},
            shield_power=200,
            weapon_power=1000,
            capacity=1500),

    Ship.battlecruiser:
        ShipData(
            cost={Resource.metal: 30000,
                  Resource.crystal: 40000,
                  Resource.deuterium: 15000},
            requirements={Technology.hyperspace_drive: 5,
                          Technology.hyperspace_technology: 5,
                          Technology.laser_technology: 12,
                          Facility.shipyard: 8},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=10000,
                    fuel_consumption=250,
                    min_level=5)},
            shield_power=400,
            weapon_power=700,
            capacity=750),

    Ship.destroyer:
        ShipData(
            cost={Resource.metal: 60000,
                  Resource.crystal: 50000,
                  Resource.deuterium: 15000},
            requirements={Technology.hyperspace_drive: 6,
                          Technology.hyperspace_technology: 5,
                          Facility.shipyard: 9},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=5000,
                    fuel_consumption=1000,
                    min_level=6)},
            shield_power=500,
            weapon_power=2000,
            capacity=2000),

    Ship.deathstar:
        ShipData(
            cost={Resource.metal: 5000000,
                  Resource.crystal: 4000000,
                  Resource.deuterium: 1000000},
            requirements={Technology.hyperspace_drive: 7,
                          Technology.hyperspace_technology: 6,
                          Technology.graviton_technology: 1,
                          Facility.shipyard: 12},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=100,
                    fuel_consumption=1,
                    min_level=7)},
            shield_power=50000,
            weapon_power=200000,
            capacity=1000000),

    Ship.bomber:
        ShipData(
            cost={Resource.metal: 50000,
                  Resource.crystal: 25000,
                  Resource.deuterium: 15000},
            requirements={Technology.impulse_drive: 6,
                          Technology.plasma_technology: 5,
                          Facility.shipyard: 6},
            drives={
                Technology.impulse_drive: DriveData(
                    speed=4000,
                    fuel_consumption=700,
                    min_level=6),
                Technology.hyperspace_drive: DriveData(
                    speed=5000,
                    fuel_consumption=700,
                    min_level=8)},
            shield_power=500,
            weapon_power=1000,
            capacity=500),

    Ship.recycler:
        ShipData(
            cost={Resource.metal: 10000,
                  Resource.crystal: 6000,
                  Resource.deuterium: 2000},
            requirements={Technology.combustion_drive: 6,
                          Technology.shielding_technology: 2,
                          Facility.shipyard: 4},
            drives={
                Technology.combustion_drive: DriveData(
                    speed=2000,
                    fuel_consumption=300,
                    min_level=6),
                Technology.impulse_drive: DriveData(
                    speed=2000,
                    fuel_consumption=600,
                    min_level=17),
                Technology.hyperspace_drive: DriveData(
                    speed=2000,
                    fuel_consumption=900,
                    min_level=15)},
            shield_power=10,
            weapon_power=1,
            capacity=20000),

    Ship.espionage_probe:
        ShipData(
            cost={Resource.crystal: 1000},
            requirements={Technology.combustion_drive: 3,
                          Technology.espionage_technology: 3,
                          Facility.shipyard: 3},
            drives={
                Technology.combustion_drive: DriveData(
                    speed=100000000,
                    fuel_consumption=1,
                    min_level=3)},
            shield_power=0,
            weapon_power=0,
            capacity=5),

    Ship.colony_ship:
        ShipData(
            cost={Resource.metal: 10000,
                  Resource.crystal: 20000,
                  Resource.deuterium: 10000},
            requirements={Technology.impulse_drive: 3,
                          Facility.shipyard: 4},
            drives={
                Technology.impulse_drive: DriveData(
                    speed=2500,
                    fuel_consumption=1000,
                    min_level=3)},
            shield_power=100,
            weapon_power=50,
            capacity=7500),

    Ship.reaper:
        ShipData(
            cost={Resource.metal: 85000,
                  Resource.crystal: 55000,
                  Resource.deuterium: 20000},
            requirements={Technology.hyperspace_drive: 7,
                          Technology.hyperspace_technology: 6,
                          Technology.shielding_technology: 6,
                          Facility.shipyard: 10},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=7000,
                    fuel_consumption=1100,
                    min_level=7)},
            shield_power=700,
            weapon_power=2800,
            capacity=10000),

    Ship.pathfinder:
        ShipData(
            cost={Resource.metal: 8000,
                  Resource.crystal: 15000,
                  Resource.deuterium: 8000},
            requirements={Technology.hyperspace_drive: 2,
                          Technology.shielding_technology: 7,
                          Facility.shipyard: 5},
            drives={
                Technology.hyperspace_drive: DriveData(
                    speed=12000,
                    fuel_consumption=300,
                    min_level=2)},
            shield_power=100,
            weapon_power=200,
            capacity=10000),
}
