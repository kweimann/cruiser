from typing import Union

import requests
import xmltodict

from ogame.api.model import (
    Player,
    Coordinates,
    Moon,
    Planet,
    Highscore,
    Alliance,
    ServerData
)
from ogame.game.const import (
    HighscoreCategory,
    HighscoreType
)
from ogame.util import (
    str2int,
    extract_numbers,
    str2bool
)


class OGameAPI:
    def __init__(self, server_number, server_language, request_timeout=10):
        self.server_number = server_number
        self.server_language = server_language
        self.request_timeout = request_timeout

    def get_players(self):
        def parse_player(player_dict):
            return Player(id=int(player_dict['@id']),
                          name=player_dict['@name'],
                          status=player_dict.get('@status'),
                          alliance_id=str2int(player_dict.get('@alliance')))

        players_dict = self._get_endpoint('players')
        timestamp = int(players_dict['@timestamp'])
        players = list(map(parse_player, players_dict['player']))
        return {'timestamp': timestamp,
                'players': players}

    def get_universe(self):
        def parse_coordinates(coords):
            galaxy, system, position = extract_numbers(coords)
            return Coordinates(galaxy, system, position)

        def parse_moon(moon_dict):
            return Moon(id=int(moon_dict['@id']),
                        name=moon_dict['@name'],
                        size=int(moon_dict['@size']))

        def parse_planet(planet_dict):
            moon_dict = planet_dict.get('moon')
            return Planet(id=int(planet_dict['@id']),
                          player_id=int(planet_dict['@player']),
                          name=planet_dict['@name'],
                          coords=parse_coordinates(planet_dict['@coords']),
                          moon=parse_moon(moon_dict) if moon_dict else None)

        universe_dict = self._get_endpoint('universe')
        timestamp = int(universe_dict['@timestamp'])
        planets = list(map(parse_planet, universe_dict['planet']))
        return {'timestamp': timestamp,
                'planets': planets}

    def get_highscore(self,
                      category: Union[HighscoreCategory, int] = HighscoreCategory.player,
                      type: Union[HighscoreType, int] = HighscoreType.points):
        def parse_highscore(player_dict):
            return Highscore(player_id=int(player_dict['@id']),
                             position=int(player_dict['@position']),
                             score=int(player_dict['@score']))

        if isinstance(category, HighscoreCategory):
            category = category.id
        if isinstance(type, HighscoreType):
            type = type.id
        highscore_dict = self._get_endpoint('highscore', params={'category': category, 'type': type})
        timestamp = int(highscore_dict['@timestamp'])
        highscores = list(map(parse_highscore, highscore_dict['player']))
        return {'timestamp': timestamp,
                'highscores': highscores}

    def get_alliances(self):
        def parse_players(players_list):
            if isinstance(players_list, list):
                return [int(player['@id']) for player in players_list]
            else:
                return [int(players_list['@id'])]

        def parse_alliance(alliance_dict):
            players_list = alliance_dict.get('player')
            return Alliance(id=int(alliance_dict['@id']),
                            name=alliance_dict['@name'],
                            tag=alliance_dict['@tag'],
                            founder_id=int(alliance_dict['@founder']),
                            creation_timestamp=int(alliance_dict['@foundDate']),
                            player_ids=parse_players(players_list) if players_list else [],
                            logo=alliance_dict.get('@logo'),
                            open=str2bool(alliances_dict.get('@open')))

        alliances_dict = self._get_endpoint('alliances')
        timestamp = int(alliances_dict['@timestamp'])
        highscores = list(map(parse_alliance, alliances_dict['alliance']))
        return {'timestamp': timestamp,
                'highscores': highscores}

    def get_localization(self):
        def parse_names(names):
            return {name['#text']: int(name['@id']) for name in names}

        localization_dict = self._get_endpoint('localization')
        timestamp = int(localization_dict['@timestamp'])
        technologies = parse_names(localization_dict['techs']['name'])
        missions = parse_names(localization_dict['missions']['name'])
        return {'timestamp': timestamp,
                'technologies': technologies,
                'missions': missions}

    def get_server_data(self):
        def parse_server_data(server_data_dict):
            return ServerData(
                name=server_data_dict['name'],
                number=int(server_data_dict['number']),
                language=server_data_dict['language'],
                timezone=server_data_dict['timezone'],
                timezone_offset=server_data_dict['timezoneOffset'],
                domain=server_data_dict['domain'],
                version=server_data_dict['version'],
                speed=int(server_data_dict['speed']),
                fleet_speed=int(server_data_dict['speedFleet']),
                galaxies=int(server_data_dict['galaxies']),
                systems=int(server_data_dict['systems']),
                acs=str2bool(server_data_dict['acs']),
                rapid_fire=str2bool(server_data_dict['rapidFire']),
                def_to_debris=str2bool(server_data_dict['defToTF']),
                debris_factor=float(server_data_dict['debrisFactor']),
                def_debris_factor=float(server_data_dict['debrisFactorDef']),
                repair_factor=float(server_data_dict['repairFactor']),
                newbie_protection_limit=int(server_data_dict['newbieProtectionLimit']),
                newbie_protection_high=int(server_data_dict['newbieProtectionHigh']),
                top_score=int(server_data_dict['topScore']),
                bonus_fields=int(server_data_dict['bonusFields']),
                donut_galaxy=str2bool(server_data_dict['donutGalaxy']),
                donut_system=str2bool(server_data_dict['donutSystem']),
                wf_enabled=str2bool(server_data_dict['wfEnabled']),
                wf_min_res_lost=int(server_data_dict['wfMinimumRessLost']),
                wf_min_loss_percentage=int(server_data_dict['wfMinimumLossPercentage']),
                wf_repairable_percentage=int(server_data_dict['wfBasicPercentageRepairable']),
                global_deuterium_save_factor=float(server_data_dict['globalDeuteriumSaveFactor']),
                bash_limit=str2bool(server_data_dict['bashlimit']),
                probe_cargo=str2bool(server_data_dict['probeCargo']),
                research_speed=int(server_data_dict['researchDurationDivisor']),
                new_account_dark_matter=int(server_data_dict['darkMatterNewAcount']),
                cargo_hyperspace_tech_percentage=int(server_data_dict['cargoHyperspaceTechMultiplier']),
                marketplace_enabled=str2bool(server_data_dict['marketplaceEnabled']),
                marketplace_metal_trade_ratio=float(server_data_dict['marketplaceBasicTradeRatioMetal']),
                marketplace_crystal_trade_ratio=float(server_data_dict['marketplaceBasicTradeRatioCrystal']),
                marketplace_deuterium_trade_ratio=float(server_data_dict['marketplaceBasicTradeRatioDeuterium']),
                marketplace_price_range_lower=float(server_data_dict['marketplacePriceRangeLower']),
                marketplace_price_range_upper=float(server_data_dict['marketplacePriceRangeUpper']),
                marketplace_tax_normal_user=float(server_data_dict['marketplaceTaxNormalUser']),
                marketplace_tax_admiral=float(server_data_dict['marketplaceTaxAdmiral']),
                marketplace_tax_cancel_offer=float(server_data_dict['marketplaceTaxCancelOffer']),
                marketplace_tax_not_sold=float(server_data_dict['marketplaceTaxNotSold']),
                marketplace_offer_timeout=int(server_data_dict['marketplaceOfferTimeout']),
                character_classes_enabled=str2bool(server_data_dict['characterClassesEnabled']),
                miner_bonus_resource_production=float(server_data_dict['minerBonusResourceProduction']),
                miner_bonus_faster_trading_ships=float(server_data_dict['minerBonusFasterTradingShips']),
                miner_bonus_increased_cargo_capacity_for_trading_ships=float(
                    server_data_dict['minerBonusIncreasedCargoCapacityForTradingShips']),
                miner_bonus_increased_additional_fleet_slots=str2bool(
                    server_data_dict['minerBonusAdditionalFleetSlots']),
                resource_buggy_production_boost=float(server_data_dict['resourceBuggyProductionBoost']),
                resource_buggy_max_production_boost=float(server_data_dict['resourceBuggyMaxProductionBoost']),
                resource_buggy_energy_consumption_per_unit=int(
                    server_data_dict['resourceBuggyEnergyConsumptionPerUnit']),
                warrior_bonus_faster_combat_ships=float(server_data_dict['warriorBonusFasterCombatShips']),
                warrior_bonus_faster_recyclers=float(server_data_dict['warriorBonusFasterRecyclers']),
                warrior_bonus_recycler_fuel_consumption=float(server_data_dict['warriorBonusRecyclerFuelConsumption']),
                combat_debris_field_limit=float(server_data_dict['combatDebrisFieldLimit']),
                explorer_bonus_research_speed=float(server_data_dict['explorerBonusIncreasedResearchSpeed']),
                explorer_bonus_increased_expedition_outcome=float(
                    server_data_dict['explorerBonusIncreasedExpeditionOutcome']),
                explorer_bonus_larger_planets=float(server_data_dict['explorerBonusLargerPlanets']),
                explorer_unit_items_per_day=int(server_data_dict['explorerUnitItemsPerDay']),
                resource_production_increase_crystal=float(
                    server_data_dict['resourceProductionIncreaseCrystalDefault']),
                resource_production_increase_crystal_pos1=float(
                    server_data_dict['resourceProductionIncreaseCrystalPos1']),
                resource_production_increase_crystal_pos2=float(
                    server_data_dict['resourceProductionIncreaseCrystalPos2']),
                resource_production_increase_crystal_pos3=float(
                    server_data_dict['resourceProductionIncreaseCrystalPos3']))

        server_data_dict = self._get_endpoint('serverData')
        timestamp = int(server_data_dict['@timestamp'])
        server_data = parse_server_data(server_data_dict)
        return {'timestamp': timestamp,
                'server_data': server_data}

    def _get_endpoint(self, endpoint, **kwargs):
        response = requests.get(self._api_url(endpoint), timeout=self.request_timeout, **kwargs)
        endpoint_data = xmltodict.parse(response.content)[endpoint]
        return endpoint_data

    def _api_url(self, endpoint):
        return f'https://s{self.server_number}-{self.server_language}.ogame.gameforge.com/api/{endpoint}.xml'
