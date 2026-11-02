"""Streamlit dashboard: comp statistics, typical boards per level and carry items."""

import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# `streamlit run` only puts this file's folder on the import path; add src/ so
# that tft_meta can be imported without setting PYTHONPATH (e.g. on Streamlit Cloud)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tft_meta.analysis.comps import (  # noqa: E402
    ROLES_DIR,
    build_boards,
    find_typical_board,
    load_unit_slots,
    summarize_comps,
)
from tft_meta.analysis.items import item_name, summarize_unit_items  # noqa: E402
from tft_meta.storage.snapshot import load_snapshot, snapshot_version  # noqa: E402

SET_NUMBER = 18
LEVELS = (8, 9, 10)
# A level's typical board is only shown if the comp reached that level this often
MIN_LEVEL_BOARDS = 20


@st.cache_data
def load_data(version: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the snapshot and group boards into comps once; Streamlit caches the result.

    The snapshot is exported from the database (python -m tft_meta.storage.snapshot),
    so the dashboard runs without a database, e.g. on Streamlit Cloud. `version`
    is only used by the cache: a new snapshot gives a new version and a reload.
    """
    tables = load_snapshot(SET_NUMBER)
    boards = build_boards(tables["participants"], tables["traits"], tables["units"], SET_NUMBER)
    return boards, tables["units"], tables["unit_items"]


def load_unit_names(set_number: int) -> pd.Series:
    """Return the display name of each character id."""
    roles = pd.read_csv(ROLES_DIR / f"unit_roles_set{set_number}.csv")
    return roles.set_index("character_id")["name"]


def trait_name(trait_id: str) -> str:
    """Strip the set prefix and suffix, e.g. DA_18_Blossom or DA_Riftbeast18."""
    return re.sub(r"^DA_(\d+_)?|\d+$", "", trait_id)


def comp_name(comp: str, unit_names: pd.Series) -> str:
    """Turn 'DA_18_Blossom + DA_18_Ahri & DA_18_Zyra' into 'Blossom Ahri & Zyra'."""
    trait, carries = comp.split(" + ")
    return trait_name(trait) + " " + " & ".join(unit_names[c] for c in carries.split(" & "))


st.set_page_config(page_title="TFT Meta Analyzer", layout="wide")
st.title("TFT Meta Analyzer")

all_boards, units, unit_items = load_data(snapshot_version(SET_NUMBER))
boards = all_boards.dropna(subset=["comp"])
unit_names = load_unit_names(SET_NUMBER)
slots = load_unit_slots(SET_NUMBER)

st.caption(
    f"Set {SET_NUMBER} ranked games from Challenger and Grandmaster players: "
    f"{boards['match_id'].nunique()} matches, {len(boards)} boards."
)

st.sidebar.header("Filters")
min_games = st.sidebar.slider("Minimum games", 20, 300, 50, step=10)
traits = sorted(boards["main_trait"].unique(), key=trait_name)
chosen_traits = st.sidebar.multiselect("Main trait", traits, format_func=trait_name)

summary = summarize_comps(boards)
summary["play_rate"] = summary["games"] / len(boards)
main_traits = boards.groupby("comp")["main_trait"].first()
summary = summary[summary["games"] >= min_games]
if chosen_traits:
    summary = summary[main_traits[summary.index].isin(chosen_traits).values]
summary = summary.sort_values("avg_placement")

st.subheader(f"Comps ({len(summary)})")
st.caption(
    f"Sorted by average placement (1-8, lower is better). Comps with fewer than "
    f"{min_games} games are hidden: with few games, one lucky or unlucky lobby "
    "changes the average a lot. Open a comp to see its typical board per level."
)


def comp_label(comp: str, stats: pd.Series) -> str:
    """Comp name followed by its statistics, shown on the collapsed row."""
    return (
        f"**{stats['tier']}** · **{comp_name(comp, unit_names)}** · "
        f"Avg place {stats['avg_placement']:.2f} · "
        f"Top 4 {stats['top4_rate']:.0%} · "
        f"Win {stats['win_rate']:.0%} · "
        f"Play rate {stats['play_rate']:.1%} · "
        f"{int(stats['games'])} games"
    )


for comp, stats in summary.iterrows():
    with st.expander(comp_label(comp, stats)):
        comp_boards = boards[boards["comp"] == comp]
        previous = None
        for level in LEVELS:
            ids = comp_boards.loc[comp_boards["level"] == level, "participant_id"]
            if len(ids) < MIN_LEVEL_BOARDS:
                continue
            board = find_typical_board(units, ids, level, slots)
            st.markdown(
                f"**Level {level}** ({len(ids)} games, avg place "
                f"{comp_boards.loc[comp_boards['level'] == level, 'placement'].mean():.2f}): "
                + ", ".join(unit_names[u] for u in board)
            )
            if previous is not None:
                added = [unit_names[u] for u in board if u not in previous]
                removed = [unit_names[u] for u in previous if u not in board]
                st.markdown(
                    f"&nbsp;&nbsp;At {level}: add {', '.join(added) or '-'}"
                    + (f"; remove {', '.join(removed)}" if removed else "")
                )
            previous = board

        for carry in comp.split(" + ")[1].split(" & "):
            items = summarize_unit_items(boards, units, unit_items, comp, carry)
            if items.empty:
                continue
            st.markdown(
                f"**{unit_names[carry]} items** (boards where it holds 3 items; "
                "no tier under 30 boards)"
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "Tier": items["tier"].fillna("–").values,
                        "Item": items.index.map(item_name),
                        "Games": items["games"].values,
                        "Avg place": items["avg_placement"].values,
                        "Place change": items["place_change"].values,
                    }
                ),
                hide_index=True,
                column_config={
                    "Avg place": st.column_config.NumberColumn(format="%.2f"),
                    "Place change": st.column_config.NumberColumn(format="%+.2f"),
                },
            )
