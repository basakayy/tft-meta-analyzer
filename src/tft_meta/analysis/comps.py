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
# Two groups are one comp if their core units overlap at least this much
MERGE_SIMILARITY = 0.8
# Smaller cores overlap too easily, so they are never merged
MIN_CORE_UNITS = 4
# A carry is named in the comp name if it carries at least this share of its boards
NAME_SHARE = 0.3
MAX_NAMED_CARRIES = 2


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


def load_unit_slots(set_number: int) -> pd.Series:
    """Return how many board slots each character id takes (Elder Dragon takes 2)."""
    roles = pd.read_csv(ROLES_DIR / f"unit_roles_set{set_number}.csv")
    return roles.set_index("character_id")["slots"]


def find_carries(units: pd.DataFrame, tank_ids: set[str]) -> pd.Series:
    """Return each player's carry: a non-tank with the most items.

    Ties first skip the most expensive units: the carry holds the items through
    the game, while top-cost units usually arrive only at the end. Remaining
    ties go to more stars, then the higher cost.
    """
    candidates = units[~units["character_id"].isin(tank_ids)].assign(
        is_top_cost=lambda frame: frame["rarity"] == frame["rarity"].max()
    )
    carries = (
        candidates.sort_values(
            ["item_count", "is_top_cost", "star_level", "rarity"],
            ascending=[False, True, False, False],
        )
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


def overlap(first: set[str], second: set[str]) -> float:
    """Shared units divided by the size of the smaller set.

    Unlike Jaccard, a comp that only adds a few units to another still scores high.
    """
    return len(first & second) / min(len(first), len(second))


def is_same_comp(first: set[str], second: set[str]) -> bool:
    """Return True if two core unit sets are big enough and overlap enough."""
    if min(len(first), len(second)) < MIN_CORE_UNITS:
        return False
    return overlap(first, second) >= MERGE_SIMILARITY


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
            (l for l in trait_leaders if is_same_comp(core[group], core[l])),
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


def name_comps(boards: pd.DataFrame) -> pd.DataFrame:
    """Rename each comp to its main trait plus its most common carries.

    A merged comp can have two clear carries (e.g. Ezreal and Aphelios), so
    every carry with at least NAME_SHARE of the boards is named, up to
    MAX_NAMED_CARRIES. If none reaches the share, the most common one is used.
    """
    shares = boards.groupby("comp")["carry"].value_counts(normalize=True)
    main_trait = boards.groupby("comp")["main_trait"].first()
    names = {}
    for comp, comp_shares in shares.groupby(level="comp"):
        top = comp_shares.head(MAX_NAMED_CARRIES)  # value_counts order: largest first
        carries = [carry for (_, carry), share in top.items() if share >= NAME_SHARE]
        carries = carries or [top.index[0][1]]
        names[comp] = main_trait[comp] + " + " + " & ".join(carries)
    return boards.assign(comp=boards["comp"].replace(names))


def summarize_comps(boards: pd.DataFrame) -> pd.DataFrame:
    """Return games, average placement, top 4 rate and win rate per comp."""
    boards = boards.assign(
        top4=boards["placement"] <= 4,
        win=boards["placement"] == 1,
    )
    return boards.groupby("comp").agg(
        games=("placement", "size"),
        avg_placement=("placement", "mean"),
        top4_rate=("top4", "mean"),
        win_rate=("win", "mean"),
    )


def find_typical_board(
    units: pd.DataFrame, participant_ids: pd.Series, level: int, slots: pd.Series
) -> list[str]:
    """Return the most common units of the given boards that fit in `level` slots."""
    board_units = units[units["participant_id"].isin(participant_ids)]
    share = board_units.groupby("character_id")["participant_id"].nunique() / len(participant_ids)

    board = []
    used = 0  # slots filled so far
    for unit in share.sort_values(ascending=False).index:
        size = slots[unit]  # 1, or 2 for Elder Dragon
        if used + size > level:
            continue  # does not fit: skip it
        board.append(unit)
        used += size
    return board


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
    return name_comps(merge_similar_comps(boards, units))
