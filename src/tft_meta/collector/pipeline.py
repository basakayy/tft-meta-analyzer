"""Collects top-league matches from Riot and saves new ones to the database.

Run with: python -m tft_meta.collector.pipeline --max-players 50 --matches-per-player 20
"""

import argparse

from tft_meta.collector.riot_client import RiotApiKeyError, RiotClient, RiotRequestError
from tft_meta.config import load_settings
from tft_meta.storage.repository import MatchRepository

TIERS = ("challenger", "grandmaster")


def get_top_players(client: RiotClient, max_players: int) -> list[str]:
    """Return the puuids of the highest-ranked players."""
    entries = []
    for tier in TIERS:
        league = client.get_league(tier)
        if league is not None:
            entries.extend(league["entries"])

    entries.sort(key=lambda entry: entry["leaguePoints"], reverse=True)
    return [entry["puuid"] for entry in entries[:max_players]]


def collect(
    client: RiotClient,
    repository: MatchRepository,
    max_players: int,
    matches_per_player: int,
) -> None:
    saved = skipped = failed = 0
    players = get_top_players(client, max_players)
    print(f"Players to process: {len(players)}")

    for number, puuid in enumerate(players, start=1):
        for match_id in client.get_match_ids(puuid, count=matches_per_player):
            # Checked before the request so saved matches cost no API calls
            if repository.has_match(match_id):
                skipped += 1
                continue

            try:
                match = client.get_match(match_id)
                if match is None:
                    failed += 1
                    continue
                repository.save_match(match)
                saved += 1
            except (RiotRequestError, KeyError) as error:
                # One bad match must not stop a long collection run
                failed += 1
                print(f"Skipped {match_id}: {error!r}")

        print(f"Player {number}/{len(players)}: saved={saved} skipped={skipped} failed={failed}")

    print(f"Done: saved={saved} skipped={skipped} failed={failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect TFT matches from the Riot API.")
    parser.add_argument("--max-players", type=int, default=50)
    parser.add_argument("--matches-per-player", type=int, default=20)
    args = parser.parse_args()

    settings = load_settings()
    repository = MatchRepository(settings.database_url)
    try:
        repository.create_tables()
        collect(RiotClient(settings), repository, args.max_players, args.matches_per_player)
    except RiotApiKeyError as error:
        print(error)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
