import pandas as pd
import pytest

from tft_meta.analysis.comps import (
    CarryRules,
    find_carries,
    find_main_traits,
    find_typical_board,
    is_same_comp,
    overlap,
    summarize_comps,
)

RULES = CarryRules(non_carry_ids={"Tank", "Support"}, top_cost_carry_ids={"Draven"})


def units_frame(rows):
    return pd.DataFrame(rows, columns=["participant_id", "character_id", "star_level", "rarity", "item_count"])


def test_main_trait_has_most_units_and_ties_go_by_name():
    traits = pd.DataFrame(
        [(1, "Blossom", 6), (1, "Fae", 3), (2, "Fae", 4), (2, "Elderwood", 4)],
        columns=["participant_id", "name", "num_units"],
    )
    assert find_main_traits(traits).to_dict() == {1: "Blossom", 2: "Elderwood"}


def test_carry_skips_tanks_and_side_carries():
    units = units_frame([(1, "Tank", 2, 1, 3), (1, "Support", 2, 3, 3), (1, "Ahri", 2, 3, 2)])
    assert find_carries(units, RULES)[1] == "Ahri"


def test_carry_tie_puts_top_cost_units_last():
    # Rarity 4 is the top cost in this data; Alune arrives late, so Ezreal is the carry
    units = units_frame([(1, "Alune", 2, 4, 3), (1, "Ezreal", 2, 3, 3)])
    assert find_carries(units, RULES)[1] == "Ezreal"


def test_top_cost_carry_is_not_skipped():
    units = units_frame([(1, "Draven", 2, 4, 3), (1, "Ezreal", 1, 3, 3)])
    assert find_carries(units, RULES)[1] == "Draven"


def test_overlap_uses_the_smaller_set():
    small = {"A", "B", "C", "D"}
    bigger = small | {"E", "F", "G"}
    assert overlap(small, bigger) == 1.0


def test_same_comp_when_carries_share_boards():
    # Azir's group plays Zyra and Zyra's group plays Azir
    assert is_same_comp({"Azir", "Zyra", "X"}, {"Zyra", "Azir", "Y"}, "Azir", "Zyra")


def test_small_cores_are_not_merged_on_overlap_alone():
    assert not is_same_comp({"A", "B", "C"}, {"A", "B", "C", "D"}, "A", "D")


def test_summary_rates_and_tiers():
    boards = pd.DataFrame({"comp": ["X"] * 4 + ["Y"] * 2, "placement": [1, 2, 3, 6, 8, 7]})
    summary = summarize_comps(boards)
    assert summary.loc["X", "games"] == 4
    assert summary.loc["X", "avg_placement"] == 3.0
    assert summary.loc["X", "top4_rate"] == 0.75
    assert summary.loc["X", "win_rate"] == 0.25
    assert summary.loc["X", "tier"] == "S"
    assert summary.loc["Y", "tier"] == "C"


def test_tier_limit_belongs_to_the_lower_tier():
    # Exactly 4.0 is A, not S
    summary = summarize_comps(pd.DataFrame({"comp": ["X", "X"], "placement": [3, 5]}))
    assert summary.loc["X", "tier"] == "A"


def test_typical_board_counts_two_slot_units():
    # Dragon, A and B are on both boards, C only on one
    rows = [(p, unit, 1, 1, 0) for p in (1, 2) for unit in ("Dragon", "A", "B")]
    units = units_frame(rows + [(1, "C", 1, 1, 0)])
    slots = pd.Series({"Dragon": 2, "A": 1, "B": 1, "C": 1})
    board = find_typical_board(units, pd.Series([1, 2]), level=4, slots=slots)
    # Dragon takes 2 of the 4 slots, so C no longer fits
    assert sorted(board) == ["A", "B", "Dragon"]


@pytest.mark.parametrize("level", [8, 9, 10])
def test_typical_board_never_exceeds_level(level):
    units = units_frame([(1, f"U{i}", 1, 1, 0) for i in range(12)])
    slots = pd.Series({f"U{i}": 1 for i in range(12)})
    assert len(find_typical_board(units, pd.Series([1]), level, slots)) == level
