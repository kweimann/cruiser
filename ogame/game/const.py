import enum


class IdEnum(enum.Enum):
    @property
    def id(self): return self.value
    def __str__(self): return self.name
    def __repr__(self): return self.name

    @classmethod
    def from_name(cls, name: str):
        value = next((value for value in cls if value.name == name), None)
        if not value:
            raise ValueError(f'{name} is not a valid field.')
        return value


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
    expedition = 15


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
    deathstar = 214
    battlecruiser = 215
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
    miner = 1
    warrior = 2
    explorer = 3


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
