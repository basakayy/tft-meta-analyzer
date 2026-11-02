from tft_meta.collector.parser import (
    parse_items,
    parse_match,
    parse_participant,
    parse_trait,
    parse_unit,
)

# A trimmed match in the shape the Riot API returns
MATCH = {
    "metadata": {"match_id": "TEST_1"},
    "info": {
        "game_datetime": 1_700_000_000_000,
        "game_length": 2100.5,
        "tft_set_number": 18,
        "queue_id": 1100,
        "game_version": "",
        "participants": [
            {
                "placement": 3,
                "level": 9,
                "units": [
                    {"character_id": "DA_18_Ahri", "tier": 2, "rarity": 4, "itemNames": ["DA_BlueBuff"]},
                    {"character_id": "DA_18_Sett", "tier": 3, "rarity": 1},
                ],
                "traits": [{"name": "DA_18_Blossom", "num_units": 6, "style": 3, "tier_current": 2}],
            }
        ],
    },
}


def test_parse_match():
    assert parse_match(MATCH) == ("TEST_1", 1_700_000_000_000, 2100.5, 18, 1100, "")


def test_parse_participant():
    assert parse_participant(MATCH["info"]["participants"][0]) == (3, 9)


def test_parse_unit_reads_star_level_from_tier():
    unit = MATCH["info"]["participants"][0]["units"][0]
    assert parse_unit(unit) == ("DA_18_Ahri", 2, 4)


def test_parse_trait():
    trait = MATCH["info"]["participants"][0]["traits"][0]
    assert parse_trait(trait) == ("DA_18_Blossom", 6, 3, 2)


def test_parse_items_handles_units_without_items():
    ahri, sett = MATCH["info"]["participants"][0]["units"]
    assert parse_items(ahri) == ["DA_BlueBuff"]
    assert parse_items(sett) == []
