"""Database access: all of the project's SQL for writing matches lives here."""

from pathlib import Path
from typing import Any

import psycopg

from tft_meta.collector.parser import (
    parse_items,
    parse_match,
    parse_participant,
    parse_trait,
    parse_unit,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class MatchRepository:
    def __init__(self, database_url: str) -> None:
        # autocommit: transactions are started explicitly in save_match
        self.connection = psycopg.connect(database_url, autocommit=True)

    def close(self) -> None:
        self.connection.close()

    def create_tables(self) -> None:
        self.connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    def has_match(self, match_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM matches WHERE match_id = %s", (match_id,)
        ).fetchone()
        return row is not None

    def save_match(self, match: dict[str, Any]) -> None:
        """Save a match and all its rows, or nothing if any step fails."""
        with self.connection.transaction():
            self.connection.execute(
                "INSERT INTO matches VALUES (%s, %s, %s, %s, %s, %s)",
                parse_match(match),
            )
            match_id = match["metadata"]["match_id"]
            for player in match["info"]["participants"]:
                self._save_participant(match_id, player)

    def _save_participant(self, match_id: str, player: dict[str, Any]) -> None:
        placement, level = parse_participant(player)
        participant_id = self.connection.execute(
            """
            INSERT INTO participants (match_id, placement, level)
            VALUES (%s, %s, %s)
            RETURNING participant_id
            """,
            (match_id, placement, level),
        ).fetchone()[0]

        for unit in player["units"]:
            self._save_unit(participant_id, unit)

        for trait in player["traits"]:
            self.connection.execute(
                """
                INSERT INTO traits (participant_id, name, num_units, style, tier_current)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (participant_id, *parse_trait(trait)),
            )

    def _save_unit(self, participant_id: int, unit: dict[str, Any]) -> None:
        unit_id = self.connection.execute(
            """
            INSERT INTO units (participant_id, character_id, star_level, rarity)
            VALUES (%s, %s, %s, %s)
            RETURNING unit_id
            """,
            (participant_id, *parse_unit(unit)),
        ).fetchone()[0]

        for item_name in parse_items(unit):
            self.connection.execute(
                "INSERT INTO items (unit_id, name) VALUES (%s, %s)",
                (unit_id, item_name),
            )
