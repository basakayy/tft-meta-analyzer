"""Turns raw Riot match data into values that fit our database tables."""

from typing import Any


def parse_participant(player: dict[str, Any]) -> tuple[int, int]:
    """Return a player's placement and level."""
    placement = player["placement"]
    level = player["level"]
    return placement, level
