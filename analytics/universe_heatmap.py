import argparse

import matplotlib.pyplot as plt
import numpy as np

from ogame import OGameAPI
from ogame.game.const import HighscoreType, HighscoreCategory

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', required=True, type=int, help='server number e.g. 1')
    parser.add_argument('--lang', required=True, help='server language e.g. en')
    parser.add_argument('--type', default='occupancy', help='heatmap type: `occupancy` (where most players are) '
                                                            'or `points` (where the strongest players are)')
    parser.add_argument('--max-position', type=int, help='when heatmap type is `points` then '
                                                         'only consider players whose position < max-position')
    args = parser.parse_args()

    # initialize API client
    api = OGameAPI(
        server_number=args.server,
        server_language=args.lang)

    # get server data
    server_data = api.get_server_data()['server_data']

    # get all planets in the universe
    planets = api.get_universe()['planets']

    # create a matrix of the universe
    universe = {}
    for planet in planets:
        galaxy = universe.setdefault(planet.coords.galaxy, {})
        system = galaxy.setdefault(planet.coords.system, [])
        system.append(planet)
    universe = [[universe.get(galaxy, {}).get(system, [])
                 for system in range(1, server_data.systems + 1)]
                for galaxy in range(1, server_data.galaxies + 1)]

    fig, ax = plt.subplots(server_data.galaxies, sharex=True, sharey=True)
    fig.suptitle(f'{server_data.name or f"Uni{server_data.number}"}.{server_data.language}')

    if args.type == 'occupancy':
        # draw heatmap showing the occupancy of the universe
        extent = [0, server_data.systems, 0, 15]
        for i, galaxy in enumerate(universe):
            galaxy_values = np.array([len(system) for system in galaxy])
            ax[i].set_title(f'G{i+1}')
            ax[i].imshow(galaxy_values[np.newaxis, :], cmap="plasma", aspect="auto", extent=extent)
            ax[i].set_yticks([])
            ax[i].set_xlim(0, server_data.systems + 1)
    elif args.type == 'points':
        # draw heatmap showing the distribution of strong players
        highscores = api.get_highscore(
            category=HighscoreCategory.player,
            type=HighscoreType.points)['highscores']
        highscores = {highscore.player_id: highscore.position for highscore in highscores}
        num_players = len(highscores)
        num_brackets = num_players // 100
        extent = [0, server_data.systems, 0, num_brackets]

        def system_score(system):
            player_positions = [highscores[planet.player_id] for planet in system
                                if planet.player_id in highscores]
            if args.max_position:
                player_positions = [position for position in player_positions
                                    if position < args.max_position]
            if player_positions:
                return min(player_positions) // 100
            else:
                return num_brackets

        for i, galaxy in enumerate(universe):
            galaxy_values = np.array([system_score(system) for system in galaxy])
            ax[i].set_title(f'G{i+1}')
            # reverse color map because smaller scores are better
            ax[i].imshow(galaxy_values[np.newaxis, :], cmap="plasma_r", aspect="auto", extent=extent)
            ax[i].set_yticks([])
            ax[i].set_xlim(0, server_data.systems + 1)
    else:
        raise ValueError(f'Unknown heatmap type: {args.type}')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()
