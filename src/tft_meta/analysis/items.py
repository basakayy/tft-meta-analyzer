"""Item statistics for a unit inside a comp: how often each item is used and its place change."""

import re

import pandas as pd

ITEM_COLUMNS = ["participant_id", "character_id", "item"]

# Items seen on fewer boards are hidden
MIN_ITEM_GAMES = 10
# Items seen on fewer boards are shown without a tier: their average is unreliable
MIN_TIER_GAMES = 30
# A unit can hold at most three items
FULL_ITEMS = 3
# Place change limits: S is below -0.30, C is +0.10 or higher
ITEM_TIER_LIMITS = [-0.30, -0.10, 0.10]
ITEM_TIERS = ["S", "A", "B", "C"]


def item_name(item_id: str) -> str:
    """Turn 'DA_GuinsoosRageblade' into 'Guinsoos Rageblade' and
    'DA_Artifact_Rapid Fire Cannon' into 'Rapid Fire Cannon'."""
    name = re.sub(r"^DA_(\d+_)?(Artifact_)?", "", item_id)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def summarize_unit_items(
    boards: pd.DataFrame,
    units: pd.DataFrame,
    unit_items: pd.DataFrame,
    comp: str,
    unit: str,
) -> pd.DataFrame:
    """Return games, average placement and place change of each item on a unit in a comp.

    Only boards where the unit holds a full set of items are used: boards with
    fewer items mostly belong to players who were knocked out early, which
    would make every item look good. Place change is the item's average
    placement minus the unit's average placement on these boards; negative
    means the item did better.
    """
    comp_boards = boards.loc[boards["comp"] == comp, ["participant_id", "placement"]]
    full_units = units[(units["character_id"] == unit) & (units["item_count"] >= FULL_ITEMS)]
    unit_boards = comp_boards[comp_boards["participant_id"].isin(full_units["participant_id"])]
    baseline = unit_boards["placement"].mean()

    holders = unit_items[unit_items["character_id"] == unit].merge(unit_boards, on="participant_id")
    # Two copies of the unit with the same item still count as one board
    holders = holders.drop_duplicates(["participant_id", "item"])
    stats = holders.groupby("item")["placement"].agg(games="size", avg_placement="mean")
    stats = stats[stats["games"] >= MIN_ITEM_GAMES]
    stats["place_change"] = stats["avg_placement"] - baseline
    # right=False: exactly -0.30 is A, exactly +0.10 is C
    tiers = pd.cut(
        stats["place_change"],
        bins=[-8, *ITEM_TIER_LIMITS, 8],
        labels=ITEM_TIERS,
        right=False,
    )
    # Empty tier for items with too few boards
    stats["tier"] = tiers.astype(object).where(stats["games"] >= MIN_TIER_GAMES)
    # Best first: S to C, items without a tier last; within a tier, best place change first
    tier_rank = stats["tier"].map({tier: rank for rank, tier in enumerate(ITEM_TIERS)})
    stats = stats.assign(tier_rank=tier_rank.fillna(len(ITEM_TIERS)))
    return stats.sort_values(["tier_rank", "place_change"]).drop(columns="tier_rank")
