"""Turns raw Riot match data into values that fit our database tables."""

from typing import Any


def parse_participant(player: dict[str, Any]) -> tuple[int, int]:
    """Return a player's placement and level."""
    placement = player["placement"]
    level = player["level"]
    return placement, level


def parse_unit(unit: dict[str, Any]) -> tuple[str, int, int]:
    """Return a unit's character id, star level and rarity."""
    character_id = unit["character_id"]
    star_level = unit["tier"]
    rarity = unit["rarity"]
    return character_id, star_level, rarity


def parse_trait(trait: dict[str, Any]) -> tuple[str, int, int, int]:
    """Return a trait's name, unit count, style and current tier."""
    name = trait["name"]
    num_units = trait["num_units"]
    style = trait["style"]
    tier_current = trait["tier_current"]
    return name, num_units, style, tier_current
