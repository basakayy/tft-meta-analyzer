import pandas as pd

from tft_meta.analysis import items
from tft_meta.analysis.items import item_name, summarize_unit_items


def test_item_name_cleans_prefixes():
    assert item_name("DA_GuinsoosRageblade") == "Guinsoos Rageblade"
    assert item_name("DA_18_EmblemBrawler") == "Emblem Brawler"
    assert item_name("DA_Artifact_Rapid Fire Cannon") == "Rapid Fire Cannon"


def make_data(monkeypatch):
    """Ten boards of one comp; the carry holds 3 items on boards 1-8 only."""
    monkeypatch.setattr(items, "MIN_ITEM_GAMES", 1)
    monkeypatch.setattr(items, "MIN_TIER_GAMES", 4)
    placements = [1, 2, 3, 4, 5, 6, 7, 8, 8, 8]
    boards = pd.DataFrame({"participant_id": range(1, 11), "comp": "C", "placement": placements})
    units = pd.DataFrame(
        {"participant_id": range(1, 11), "character_id": "Carry", "item_count": [3] * 8 + [1, 1]}
    )
    # Good item on the top 4 boards, other item on boards 5-8 and the two 1-item boards
    held = [(p, "Carry", "DA_Good") for p in range(1, 5)] + [
        (p, "Carry", "DA_Other") for p in range(5, 11)
    ]
    unit_items = pd.DataFrame(held, columns=["participant_id", "character_id", "item"])
    return boards, units, unit_items


def test_place_change_uses_full_item_boards_only(monkeypatch):
    stats = summarize_unit_items(*make_data(monkeypatch), comp="C", unit="Carry")
    # Baseline is boards 1-8 (average 4.5); the two 1-item boards are left out
    assert stats.loc["DA_Good", "games"] == 4
    assert stats.loc["DA_Good", "place_change"] == 2.5 - 4.5
    assert stats.loc["DA_Other", "games"] == 4
    assert stats.loc["DA_Other", "place_change"] == 6.5 - 4.5


def test_items_are_sorted_best_tier_first(monkeypatch):
    stats = summarize_unit_items(*make_data(monkeypatch), comp="C", unit="Carry")
    assert list(stats.index) == ["DA_Good", "DA_Other"]
    assert list(stats["tier"]) == ["S", "C"]
