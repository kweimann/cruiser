from ogame.game.const import (
    Ship,
    Resource,
    Technology
)

SHIP = {
    Ship.small_cargo: {
        'base_cost': {
            Resource.metal: 2000,
            Resource.crystal: 2000
        },
        'requirements': {
            'technology': {
                'combustion_drive': 2,
            },
            'facilities': {
                'shipyard': 2
            }
        },
        'drives': {
            Technology.combustion_drive: {
                'min_level': 2,
                'base_speed': 5000,
                'base_fuel_consumption': 10
            },
            Technology.impulse_drive: {
                'min_level': 5,
                'base_speed': 10000,
                'base_fuel_consumption': 20
            }
        },
        'shield_power': 10,
        'weapon_power': 5,
        'cargo_capacity': 5000,
    },

    Ship.large_cargo: {
        'base_cost': {
            Resource.metal: 6000,
            Resource.crystal: 6000
        },
        'requirements': {
            'technology': {
                'combustion_drive': 6
            },
            'facilities': {
                'shipyard': 4
            }
        },
        'drives': {
            Technology.combustion_drive: {
                'min_level': 6,
                'base_speed': 7500,
                'base_fuel_consumption': 50
            }
        },
        'shield_power': 25,
        'weapon_power': 5,
        'cargo_capacity': 25000,
    },

    Ship.light_fighter: {
        'base_cost': {
            Resource.metal: 3000,
            Resource.crystal: 1000
        },
        'requirements': {
            'technology': {
                'combustion_drive': 1
            },
            'facilities': {
                'shipyard': 1
            }
        },
        'drives': {
            Technology.combustion_drive: {
                'min_level': 1,
                'base_speed': 12500,
                'base_fuel_consumption': 20
            }
        },
        'shield_power': 10,
        'weapon_power': 50,
        'cargo_capacity': 50
    },

    Ship.heavy_fighter: {
        'base_cost': {
            Resource.metal: 6000,
            Resource.crystal: 4000
        },
        'requirements': {
            'technology': {
                'impulse_drive': 2,
                'armour_technology': 2
            },
            'facilities': {
                'shipyard': 3
            }
        },
        'drives': {
            Technology.impulse_drive: {
                'min_level': 2,
                'base_speed': 10000,
                'base_fuel_consumption': 75
            }
        },
        'shield_power': 25,
        'weapon_power': 150,
        'cargo_capacity': 100,
    },

    Ship.cruiser: {
        'base_cost': {
            Resource.metal: 20000,
            Resource.crystal: 7000,
            Resource.deuterium: 2000
        },
        'requirements': {
            'technology': {
                'impulse_drive': 4,
                'ion_technology': 2
            },
            'facilities': {
                'shipyard': 5
            }
        },
        'drives': {
            Technology.impulse_drive: {
                'min_level': 4,
                'base_speed': 15000,
                'base_fuel_consumption': 300
            }
        },
        'shield_power': 50,
        'weapon_power': 400,
        'cargo_capacity': 800,
    },

    Ship.battleship: {
        'base_cost': {
            Resource.metal: 45000,
            Resource.crystal: 15000
        },
        'requirements': {
            'technology': {
                'hyperspace_drive': 4
            },
            'facilities': {
                'shipyard': 7
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 4,
                'base_speed': 10000,
                'base_fuel_consumption': 500
            }
        },
        'shield_power': 200,
        'weapon_power': 1000,
        'cargo_capacity': 1500,
    },

    Ship.battlecruiser: {
        'base_cost': {
            Resource.metal: 30000,
            Resource.crystal: 40000,
            Resource.deuterium: 15000
        },
        'requirements': {
            'technology': {
                'hyperspace_technology': 5,
                'hyperspace_drive': 5,
                'laser_technology': 12
            },
            'facilities': {
                'shipyard': 8
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 5,
                'base_speed': 10000,
                'base_fuel_consumption': 250
            }
        },
        'shield_power': 400,
        'weapon_power': 700,
        'cargo_capacity': 750,
    },

    Ship.destroyer: {
        'base_cost': {
            Resource.metal: 60000,
            Resource.crystal: 50000,
            Resource.deuterium: 15000
        },
        'requirements': {
            'technology': {
                'hyperspace_technology': 5,
                'hyperspace_drive': 6
            },
            'facilities': {
                'shipyard': 9
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 6,
                'base_speed': 5000,
                'base_fuel_consumption': 1000
            }
        },
        'shield_power': 500,
        'weapon_power': 2000,
        'cargo_capacity': 2000,
    },

    Ship.deathstar: {
        'base_cost': {
            Resource.metal: 5000000,
            Resource.crystal: 4000000,
            Resource.deuterium: 1000000
        },
        'requirements': {
            'technology': {
                'graviton_technology': 1,
                'hyperspace_technology': 6,
                'hyperspace_drive': 7
            },
            'facilities': {
                'shipyard': 12
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 7,
                'base_speed': 100,
                'base_fuel_consumption': 1
            }
        },
        'shield_power': 50000,
        'weapon_power': 200000,
        'cargo_capacity': 1000000,
    },

    Ship.bomber: {
        'base_cost': {
            Resource.metal: 50000,
            Resource.crystal: 25000,
            Resource.deuterium: 15000
        },
        'requirements': {
            'technology': {
                'plasma_technology': 5,
                'impulse_drive': 6
            },
            'facilities': {
                'shipyard': 6
            }
        },
        'drives': {
            Technology.impulse_drive: {
                'min_level': 6,
                'base_speed': 4000,
                'base_fuel_consumption': 700
            },
            Technology.hyperspace_drive: {
                'min_level': 8,
                'base_speed': 5000,
                'base_fuel_consumption': 700
            }
        },
        'shield_power': 500,
        'weapon_power': 1000,
        'cargo_capacity': 500,
    },

    Ship.recycler: {
        'base_cost': {
            Resource.metal: 10000,
            Resource.crystal: 6000,
            Resource.deuterium: 2000
        },
        'requirements': {
            'technology': {
                'combustion_drive': 6,
                'shielding_technology': 2
            },
            'facilities': {
                'shipyard': 4
            }
        },
        'drives': {
            Technology.combustion_drive: {
                'min_level': 6,
                'base_speed': 2000,
                'base_fuel_consumption': 300
            },
            Technology.impulse_drive: {
                'min_level': 17,
                'base_speed': 2000,
                'base_fuel_consumption': 600
            },
            Technology.hyperspace_drive: {
                'min_level': 15,
                'base_speed': 2000,
                'base_fuel_consumption': 900
            }
        },
        'shield_power': 10,
        'weapon_power': 1,
        'cargo_capacity': 20000,
    },

    Ship.espionage_probe: {
        'base_cost': {
            Resource.crystal: 1000
        },
        'requirements': {
            'technology': {
                'combustion_drive': 3,
                'espionage_technology': 3
            },
            'facilities': {
                'shipyard': 3
            }
        },
        'drives': {
            Technology.combustion_drive: {
                'min_level': 3,
                'base_speed': 100000000,
                'base_fuel_consumption': 1
            }
        },
        'shield_power': 0,
        'weapon_power': 0,
        'cargo_capacity': 5,
    },

    Ship.colony_ship: {
        'base_cost': {
            Resource.metal: 10000,
            Resource.crystal: 20000,
            Resource.deuterium: 10000
        },
        'requirements': {
            'technology': {
                'impulse_drive': 3
            },
            'facilities': {
                'shipyard': 4
            }
        },
        'drives': {
            Technology.impulse_drive: {
                'min_level': 3,
                'base_speed': 2500,
                'base_fuel_consumption': 1000
            }
        },
        'shield_power': 100,
        'weapon_power': 50,
        'cargo_capacity': 7500,
    },

    Ship.reaper: {
        'base_cost': {
            Resource.metal: 85000,
            Resource.crystal: 55000,
            Resource.deuterium: 20000
        },
        'requirements': {
            'technology': {
                'hyperspace_technology': 6,
                'hyperspace_drive': 7,
                'shielding_technology': 6
            },
            'facilities': {
                'shipyard': 10
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 7,
                'base_speed': 7000,
                'base_fuel_consumption': 1100
            }
        },
        'shield_power': 700,
        'weapon_power': 2800,
        'cargo_capacity': 10000
    },

    Ship.pathfinder: {
        'base_cost': {
            Resource.metal: 8000,
            Resource.crystal: 15000,
            Resource.deuterium: 8000
        },
        'requirements': {
            'technology': {
                'hyperspace_drive': 2,
                'shielding_technology': 7
            },
            'facilities': {
                'shipyard': 5
            }
        },
        'drives': {
            Technology.hyperspace_drive: {
                'min_level': 2,
                'base_speed': 12000,
                'base_fuel_consumption': 300
            }
        },
        'shield_power': 100,
        'weapon_power': 200,
        'cargo_capacity': 10000
    }
}

TECHNOLOGY = {
    Technology.combustion_drive: {
        'base_cost': {
            Resource.metal: 400,
            Resource.deuterium: 600
        },
        'requirements': {
            'technology': {
                'energy_technology': 1,
            },
            'facilities': {
                'research_lab': 1
            }
        },
        'speed_multiplier': 0.1
    },

    Technology.impulse_drive: {
        'base_cost': {
            Resource.metal: 2000,
            Resource.crystal: 4000,
            Resource.deuterium: 600
        },
        'requirements': {
            'technology': {
                'energy_technology': 1,
            },
            'facilities': {
                'research_lab': 2
            }
        },
        'speed_multiplier': 0.2
    },

    Technology.hyperspace_drive: {
        'base_cost': {
            Resource.metal: 10000,
            Resource.crystal: 20000,
            Resource.deuterium: 6000
        },
        'requirements': {
            'technology': {
                'energy_technology': 5,
                'shielding_technology': 5,
                'hyperspace_technology': 3
            },
            'facilities': {
                'research_lab': 7
            }
        },
        'speed_multiplier': 0.3
    },
}
