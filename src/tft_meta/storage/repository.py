"""Database access: all of the project's SQL lives here."""

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

    def load_participants(self, set_number: int, queue_id: int) -> list[tuple]:
        """Return (participant_id, match_id, placement, level) for one set and queue."""
        return self.connection.execute(
            """
            SELECT p.participant_id, p.match_id, p.placement, p.level
            FROM participants p
            JOIN matches m USING (match_id)
            WHERE m.set_number = %s AND m.queue_id = %s
            """,
            (set_number, queue_id),
        ).fetchall()

    def load_active_traits(self, set_number: int, queue_id: int) -> list[tuple]:
        """Return (participant_id, trait name, num_units) for active traits only."""
        return self.connection.execute(
            """
            SELECT t.participant_id, t.name, t.num_units
            FROM traits t
            JOIN participants p USING (participant_id)
            JOIN matches m USING (match_id)
            WHERE m.set_number = %s AND m.queue_id = %s AND t.style > 0
            """,
            (set_number, queue_id),
        ).fetchall()

    def load_units(self, set_number: int, queue_id: int) -> list[tuple]:
        """Return (participant_id, character_id, star_level, rarity, item_count) per unit."""
        return self.connection.execute(
            """
            SELECT u.participant_id, u.character_id, u.star_level, u.rarity,
                   COUNT(i.item_id) AS item_count
            FROM units u
            JOIN participants p USING (participant_id)
            JOIN matches m USING (match_id)
            LEFT JOIN items i USING (unit_id)
            WHERE m.set_number = %s AND m.queue_id = %s
            GROUP BY u.unit_id
            """,
            (set_number, queue_id),
        ).fetchall()

    def load_unit_items(self, set_number: int, queue_id: int) -> list[tuple]:
        """Return (participant_id, character_id, item name) per equipped item."""
        return self.connection.execute(
            """
            SELECT u.participant_id, u.character_id, i.name
            FROM items i
            JOIN units u USING (unit_id)
            JOIN participants p USING (participant_id)
            JOIN matches m USING (match_id)
            WHERE m.set_number = %s AND m.queue_id = %s
            """,
            (set_number, queue_id),
        ).fetchall()

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
