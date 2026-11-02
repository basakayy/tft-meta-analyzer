"""Export the analysis tables to small files so the dashboard can run without a database.

Match ids are replaced by plain numbers: a Riot match id leads back to the
players of that match, and the analysis only needs to know which boards
were in the same game.
"""

import argparse
from pathlib import Path

import pandas as pd

from tft_meta.analysis.comps import PARTICIPANT_COLUMNS, TRAIT_COLUMNS, UNIT_COLUMNS
from tft_meta.analysis.items import ITEM_COLUMNS
from tft_meta.config import PROJECT_ROOT, load_settings
from tft_meta.storage.repository import MatchRepository

SNAPSHOT_DIR = PROJECT_ROOT / "snapshot"
RANKED_QUEUE_ID = 1100


def snapshot_path(set_number: int, table: str) -> Path:
    """Return the file of one table, e.g. snapshot/set18/units.csv.gz."""
    return SNAPSHOT_DIR / f"set{set_number}" / f"{table}.csv.gz"


def export_snapshot(repository: MatchRepository, set_number: int) -> None:
    """Write the participants, traits, units and items of a set's ranked games."""
    queue_id = RANKED_QUEUE_ID
    participants = pd.DataFrame(
        repository.load_participants(set_number, queue_id), columns=PARTICIPANT_COLUMNS
    )
    # factorize gives each distinct match id a number: 0, 1, 2, ...
    participants["match_id"] = pd.factorize(participants["match_id"])[0]
    tables = {
        "participants": participants,
        "traits": pd.DataFrame(
            repository.load_active_traits(set_number, queue_id), columns=TRAIT_COLUMNS
        ),
        "units": pd.DataFrame(repository.load_units(set_number, queue_id), columns=UNIT_COLUMNS),
        "unit_items": pd.DataFrame(
            repository.load_unit_items(set_number, queue_id), columns=ITEM_COLUMNS
        ),
    }
    for table, frame in tables.items():
        path = snapshot_path(set_number, table)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)  # .gz in the name makes pandas compress it
        print(f"{path.relative_to(PROJECT_ROOT)}: {len(frame)} rows")


SNAPSHOT_TABLES = ("participants", "traits", "units", "unit_items")


def load_snapshot(set_number: int) -> dict[str, pd.DataFrame]:
    """Read the tables written by export_snapshot."""
    return {table: pd.read_csv(snapshot_path(set_number, table)) for table in SNAPSHOT_TABLES}


def snapshot_version(set_number: int) -> float:
    """Return the latest modification time of the snapshot files.

    It changes whenever the snapshot is exported or pulled again, so caches
    keyed on it know when to reload.
    """
    return max(snapshot_path(set_number, table).stat().st_mtime for table in SNAPSHOT_TABLES)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export analysis tables for the dashboard.")
    parser.add_argument("--set-number", type=int, default=18)
    args = parser.parse_args()

    repository = MatchRepository(load_settings().database_url)
    try:
        export_snapshot(repository, args.set_number)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
