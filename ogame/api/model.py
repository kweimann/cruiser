import dataclasses
from typing import List


@dataclasses.dataclass(frozen=True)
class Player:
    id: int
    name: str
    status: str = None
    alliance_id: int = None


@dataclasses.dataclass(frozen=True)
class Moon:
    id: int
    name: str
    size: int


@dataclasses.dataclass(order=True, frozen=True)
class Coordinates:
    galaxy: int
    system: int
    position: int


@dataclasses.dataclass(frozen=True)
class Planet:
    id: int
    player_id: int
    name: str
    coords: Coordinates
    moon: Moon = None


@dataclasses.dataclass(frozen=True)
class Highscore:
    player_id: int
    position: int
    score: int


@dataclasses.dataclass(frozen=True)
class Alliance:
    id: int
    name: str
    tag: str
    founder_id: int
    creation_timestamp: int
    player_ids: List[int]
    logo: str = None
    open: bool = None


@dataclasses.dataclass(frozen=True)
class ServerData:
    name: str
    number: int
    language: str
    timezone: str
    timezone_offset: str
    domain: str
    version: str
    speed: int
    fleet_speed: int
    galaxies: int
    systems: int
    acs: bool
    rapid_fire: bool
    def_to_debris: bool
    debris_factor: float
    def_debris_factor: float
    repair_factor: float
    newbie_protection_limit: int
    newbie_protection_high: int
    top_score: int
    bonus_fields: int
    donut_galaxy: bool
    donut_system: bool
    wf_enabled: bool
    wf_min_res_lost: int
    wf_min_loss_percentage: int
    wf_repairable_percentage: int
    global_deuterium_save_factor: float
    bash_limit: bool
    probe_cargo: bool
    research_speed: int
    new_account_dark_matter: int
    cargo_hyperspace_tech_percentage: int
    marketplace_enabled: bool
    marketplace_metal_trade_ratio: float
    marketplace_crystal_trade_ratio: float
    marketplace_deuterium_trade_ratio: float
    marketplace_price_range_lower: float
    marketplace_price_range_upper: float
    marketplace_tax_normal_user: float
    marketplace_tax_admiral: float
    marketplace_tax_cancel_offer: float
    marketplace_tax_not_sold: float
    marketplace_offer_timeout: int
    character_classes_enabled: bool
    miner_bonus_resource_production: float
    miner_bonus_faster_trading_ships: float
    miner_bonus_increased_cargo_capacity_for_trading_ships: float
    miner_bonus_increased_additional_fleet_slots: int
    resource_buggy_production_boost: float
    resource_buggy_max_production_boost: float
    resource_buggy_energy_consumption_per_unit: int
    warrior_bonus_faster_combat_ships: float
    warrior_bonus_faster_recyclers: float
    warrior_bonus_recycler_fuel_consumption: float
    combat_debris_field_limit: float
    explorer_bonus_research_speed: float
    explorer_bonus_increased_expedition_outcome: float
    explorer_bonus_larger_planets: float
    explorer_unit_items_per_day: int
    resource_production_increase_crystal: float
    resource_production_increase_crystal_pos1: float
    resource_production_increase_crystal_pos2: float
    resource_production_increase_crystal_pos3: float
