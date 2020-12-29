import enum


class IdEnum(enum.Enum):
    @property
    def id(self): return self.value
    def __str__(self): return self.name
    def __repr__(self): return self.name

    @classmethod
    def from_name(cls, name: str):
        return next((e for e in cls if e.name == name), None)

    @classmethod
    def from_id(cls, id):
        return next((e for e in cls if e.id == id), None)


@enum.unique
class Mission(IdEnum):
    attack = 1
    acs_attack = 2
    transport = 3
    deployment = 4
    defend = 5
    espionage = 6
    colonization = 7
    harvest = 8
    destroy = 9
    missile = 10
    expedition = 15
    trade = 16


@enum.unique
class CoordsType(IdEnum):
    planet = 1
    debris = 2
    moon = 3


@enum.unique
class Ship(IdEnum):
    small_cargo = 202
    large_cargo = 203
    light_fighter = 204
    heavy_fighter = 205
    cruiser = 206
    battleship = 207
    colony_ship = 208
    recycler = 209
    espionage_probe = 210
    bomber = 211
    destroyer = 213
    solar_satellite = 212
    deathstar = 214
    battlecruiser = 215
    trade_ship = 216
    crawler = 217
    reaper = 218
    pathfinder = 219


class Resource(IdEnum):
    metal = object()
    crystal = object()
    deuterium = object()
    energy = object()
    dark_matter = object()


@enum.unique
class CharacterClass(IdEnum):
    collector = 1
    general = 2
    discoverer = 3


@enum.unique
class Technology(IdEnum):
    energy_technology = 113
    laser_technology = 120
    ion_technology = 121
    hyperspace_technology = 114
    plasma_technology = 122
    espionage_technology = 106
    computer_technology = 108
    astrophysics = 124
    intergalactic_research_network = 123
    graviton_technology = 199
    combustion_drive = 115
    impulse_drive = 117
    hyperspace_drive = 118
    weapons_technology = 109
    shielding_technology = 110
    armour_technology = 111


@enum.unique
class HighscoreCategory(IdEnum):
    player = 1
    alliance = 2


@enum.unique
class HighscoreType(IdEnum):
    points = 0
    economy = 1
    technology = 2
    military = 3
    military_lost = 4
    military_built = 5
    military_destroyed = 6
    honor = 7


@enum.unique
class Supply(IdEnum):
    metal_mine = 1
    metal_storage = 22
    crystal_mine = 2
    crystal_storage = 23
    deuterium_synthesizer = 3
    deuterium_tank = 24
    solar_plant = 4
    fusion_reactor = 12
    solar_satellite = 212
    crawler = 217


@enum.unique
class Facility(IdEnum):
    robotics_factory = 14
    nanite_factory = 15
    shipyard = 21
    space_dock = 36
    missile_silo = 44
    research_lab = 31
    alliance_depot = 34
    terraformer = 33
    lunar_base = 41
    sensor_phalanx = 42
    jump_gate = 43


@enum.unique
class Defense(IdEnum):
    rocket_launcher = 401
    light_laser = 402
    heavy_laser = 403
    ion_cannon = 405
    gauss_cannon = 404
    plasma_turret = 406
    small_shield_dome = 407
    large_shield_dome = 408
    anti_ballistic_missile = 502
    interplanetary_missile = 503
