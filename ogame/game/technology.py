
TECHNOLOGY = {
    'combustion_drive': {
        'id': 115,
        'base_cost': {
            'metal': 400,
            'deuterium': 600
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

    'impulse_drive': {
        'id': 117,
        'base_cost': {
            'metal': 2000,
            'crystal': 4000,
            'deuterium': 600
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

    'hyperspace_drive': {
        'id': 118,
        'base_cost': {
            'metal': 10000,
            'crystal': 20000,
            'deuterium': 6000
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

    'hyperspace_technology': {
        'id': 114,
        'base_cost': {
            'crystal': 4000,
            'deuterium': 2000
        },
        'requirements': {
            'technology': {
                'shielding_technology': 5,
                'energy_technology': 5
            },
            'facilities': {
                'research_lab': 7
            }
        },
        'cargo_capacity_multiplier': 0.05
    }
}