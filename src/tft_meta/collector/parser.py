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
