"""Groups players' final boards into comps named by main trait and carry."""

import pandas as pd

from tft_meta.config import PROJECT_ROOT
from tft_meta.storage.repository import MatchRepository

# Unit roles per set, taken from the champion list on blitz.gg
ROLES_DIR = PROJECT_ROOT / "reference"

PARTICIPANT_COLUMNS = ["participant_id", "match_id", "placement", "level"]
TRAIT_COLUMNS = ["participant_id", "name", "num_units"]
UNIT_COLUMNS = ["participant_id", "character_id", "star_level", "rarity", "item_count"]

# A unit is "core" to a group if it appears on at least this share of its boards
CORE_SHARE = 0.5
# Groups with fewer games have unreliable core units and are not merged
MIN_GROUP_GAMES = 20
# Two groups are one comp if their core units overlap at least this much (Jaccard)
MERGE_SIMILARITY = 0.7


def find_main_traits(traits: pd.DataFrame) -> pd.Series:
    """Return each player's active trait with the most units; ties go by name."""
    main = (
        traits.sort_values(["num_units", "name"], ascending=[False, True])
        .groupby("participant_id")
        .head(1)
    )
    return main.set_index("participant_id")["name"].rename("main_trait")


def load_tank_ids(set_number: int) -> set[str]:
    """Return the character ids whose role is a tank in the given set."""
    roles = pd.read_csv(ROLES_DIR / f"unit_roles_set{set_number}.csv")
    return set(roles.loc[roles["role"].str.endswith("Tank"), "character_id"])


def find_carries(units: pd.DataFrame, tank_ids: set[str]) -> pd.Series:
    """Return each player's carry: a non-tank with the most items, then stars, then cost."""
    candidates = units[~units["character_id"].isin(tank_ids)]
    carries = (
        candidates.sort_values(["item_count", "star_level", "rarity"], ascending=False)
        .groupby("participant_id")
        .head(1)
    )
    return carries.set_index("participant_id")["character_id"].rename("carry")


def assign_comps(
    participants: pd.DataFrame,
    traits: pd.DataFrame,
    units: pd.DataFrame,
    tank_ids: set[str],
) -> pd.DataFrame:
    """Add main_trait, carry and comp columns; comp is empty if either is missing."""
    boards = participants.join(find_main_traits(traits), on="participant_id")
    boards = boards.join(find_carries(units, tank_ids), on="participant_id")
    boards["comp"] = boards["main_trait"] + " + " + boards["carry"]
    return boards


def find_core_units(boards: pd.DataFrame, units: pd.DataFrame) -> dict[str, set[str]]:
    """Return the units that appear on at least CORE_SHARE of each comp's boards."""
    merged = units.merge(boards[["participant_id", "comp"]], on="participant_id")
    boards_per_comp = boards.groupby("comp")["participant_id"].nunique()
    unit_boards = merged.groupby(["comp", "character_id"])["participant_id"].nunique()
    share = unit_boards / boards_per_comp.reindex(unit_boards.index.get_level_values("comp")).values
    core = share[share >= CORE_SHARE].reset_index()
    return core.groupby("comp")["character_id"].agg(set).to_dict()


def jaccard(first: set[str], second: set[str]) -> float:
    """Shared units divided by all distinct units of both sets."""
    return len(first & second) / len(first | second)


def merge_similar_comps(boards: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """Merge groups with the same main trait whose core units mostly overlap.

    Each group is compared with the leader (most played group) of every comp
    found so far, never with other members, so unrelated groups cannot be
    chained together through a middle group.
    """
    games = boards["comp"].value_counts()
    big_groups = games[games >= MIN_GROUP_GAMES].index
    core = find_core_units(boards[boards["comp"].isin(big_groups)], units)
    main_trait = boards.groupby("comp")["main_trait"].first()

    renames = {}
    leaders: dict[str, list[str]] = {}
    for group in big_groups:  # value_counts order: most played first
        trait_leaders = leaders.setdefault(main_trait[group], [])
        leader = next(
            (l for l in trait_leaders if jaccard(core[group], core[l]) >= MERGE_SIMILARITY),
            None,
        )
        if leader is None:
            trait_leaders.append(group)
        else:
            renames[group] = leader

    boards = boards.copy()
    boards["variant"] = boards["comp"]
    boards["comp"] = boards["comp"].replace(renames)
    return boards


def load_boards(repository: MatchRepository, set_number: int, queue_id: int) -> pd.DataFrame:
    """Return one row per player with their placement, level and comp."""
    participants = pd.DataFrame(
        repository.load_participants(set_number, queue_id), columns=PARTICIPANT_COLUMNS
    )
    traits = pd.DataFrame(
        repository.load_active_traits(set_number, queue_id), columns=TRAIT_COLUMNS
    )
    units = pd.DataFrame(repository.load_units(set_number, queue_id), columns=UNIT_COLUMNS)
    boards = assign_comps(participants, traits, units, load_tank_ids(set_number))
    return merge_similar_comps(boards, units)
