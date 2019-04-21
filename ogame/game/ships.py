
SHIPS = {
    'small_cargo': {
        'id': 202,
        'base_cost': {
            'metal': 2000,
            'crystal': 2000
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
            'combustion_drive': {
                'min_level': 2,
                'base_speed': 5000,
                'base_fuel_consumption': 10
            },
            'impulse_drive': {
                'min_level': 5,
                'base_speed': 10000,
                'base_fuel_consumption': 20
            }
        },
        'shield_power': 10,
        'weapon_power': 5,
        'cargo_capacity': 5000,
    },

    'large_cargo': {
        'id': 203,
        'base_cost': {
            'metal': 6000,
            'crystal': 6000
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
            'combustion_drive': {
                'min_level': 6,
                'base_speed': 7500,
                'base_fuel_consumption': 50
            }
        },
        'shield_power': 25,
        'weapon_power': 5,
        'cargo_capacity': 25000,
    },

    'light_fighter': {
        'id': 204,
        'base_cost': {
            'metal': 3000,
            'crystal': 1000
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
            'combustion_drive': {
                'min_level': 1,
                'base_speed': 12500,
                'base_fuel_consumption': 20
            }
        },
        'shield_power': 10,
        'weapon_power': 50,
        'cargo_capacity': 50
    },

    'heavy_fighter': {
        'id': 205,
        'base_cost': {
            'metal': 6000,
            'crystal': 4000
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
            'impulse_drive': {
                'min_level': 2,
                'base_speed': 10000,
                'base_fuel_consumption': 75
            }
        },
        'shield_power': 25,
        'weapon_power': 150,
        'cargo_capacity': 100,
    },

    'cruiser': {
        'id': 206,
        'base_cost': {
            'metal': 20000,
            'crystal': 7000,
            'deuterium': 2000
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
            'impulse_drive': {
                'min_level': 4,
                'base_speed': 15000,
                'base_fuel_consumption': 300
            }
        },
        'shield_power': 50,
        'weapon_power': 400,
        'cargo_capacity': 800,
    },

    'battleship': {
        'id': 207,
        'base_cost': {
            'metal': 45000,
            'crystal': 15000
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
            'hyperspace_drive': {
                'min_level': 4,
                'base_speed': 10000,
                'base_fuel_consumption': 500
            }
        },
        'shield_power': 200,
        'weapon_power': 1000,
        'cargo_capacity': 1500,
    },

    'battlecruiser': {
        'id': 215,
        'base_cost': {
            'metal': 30000,
            'crystal': 40000,
            'deuterium': 15000
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
            'hyperspace_drive': {
                'min_level': 5,
                'base_speed': 10000,
                'base_fuel_consumption': 250
            }
        },
        'shield_power': 400,
        'weapon_power': 700,
        'cargo_capacity': 750,
    },

    'destroyer': {
        'id': 213,
        'base_cost': {
            'metal': 60000,
            'crystal': 50000,
            'deuterium': 15000
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
            'hyperspace_drive': {
                'min_level': 6,
                'base_speed': 5000,
                'base_fuel_consumption': 1000
            }
        },
        'shield_power': 500,
        'weapon_power': 2000,
        'cargo_capacity': 2000,
    },

    'deathstar': {
        'id': 214,
        'base_cost': {
            'metal': 5000000,
            'crystal': 4000000,
            'deuterium': 1000000
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
            'hyperspace_drive': {
                'min_level': 7,
                'base_speed': 100,
                'base_fuel_consumption': 1
            }
        },
        'shield_power': 50000,
        'weapon_power': 200000,
        'cargo_capacity': 1000000,
    },

    'bomber': {
        'id': 211,
        'base_cost': {
            'metal': 50000,
            'crystal': 25000,
            'deuterium': 15000
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
            'impulse_drive': {
                'min_level': 6,
                'base_speed': 4000,
                'base_fuel_consumption': 1000
            },
            'hyperspace_drive': {
                'min_level': 8,
                'base_speed': 5000,
                'base_fuel_consumption': 1000
            }
        },
        'shield_power': 500,
        'weapon_power': 1000,
        'cargo_capacity': 500,
    },

    'recycler': {
        'id': 209,
        'base_cost': {
            'metal': 10000,
            'crystal': 6000,
            'deuterium': 2000
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
            'combustion_drive': {
                'min_level': 6,
                'base_speed': 2000,
                'base_fuel_consumption': 300
            }
        },
        'shield_power': 10,
        'weapon_power': 1,
        'cargo_capacity': 20000,
    },

    'espionage_probe': {
        'id': 210,
        'base_cost': {
            'crystal': 1000
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
            'combustion_drive': {
                'min_level': 3,
                'base_speed': 100000000,
                'base_fuel_consumption': 1
            }
        },
        'shield_power': 0,
        'weapon_power': 0,
        'cargo_capacity': 5,
    },

    'colony_ship': {
        'id': 208,
        'base_cost': {
            'metal': 10000,
            'crystal': 20000,
            'deuterium': 10000
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
            'impulse_drive': {
                'min_level': 4,
                'base_speed': 2500,
                'base_fuel_consumption': 1000
            }
        },
        'shield_power': 100,
        'weapon_power': 50,
        'cargo_capacity': 7500,
    },
}
