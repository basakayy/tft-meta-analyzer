"""The only module that talks to the Riot TFT API."""

import time
from typing import Any

import requests

from tft_meta.collector.rate_limiter import RateLimiter
from tft_meta.config import Settings

DEV_KEY_LIMITS = [(20, 1), (100, 120)]
MAX_ATTEMPTS = 5
REQUEST_TIMEOUT_SECONDS = 10
TEMPORARY_STATUS_CODES = {500, 502, 503, 504}


class RiotApiKeyError(Exception):
    """The API key is invalid or expired; retrying cannot help."""


class RiotRequestError(Exception):
    """A request failed for good, even after retries."""


class RiotClient:
    def __init__(self, settings: Settings) -> None:
        self.platform_url = f"https://{settings.platform}.api.riotgames.com"
        self.region_url = f"https://{settings.region}.api.riotgames.com"
        self.limiter = RateLimiter(DEV_KEY_LIMITS)
        self.session = requests.Session()
        # Sent as a header so the key never appears in a URL or log
        self.session.headers["X-Riot-Token"] = settings.riot_api_key

    def get_league(self, tier: str) -> dict[str, Any] | None:
        """Return a league's players; tier is 'challenger' or 'grandmaster'."""
        return self._get(f"{self.platform_url}/tft/league/v1/{tier}")

    def get_match_ids(self, puuid: str, count: int = 20) -> list[str]:
        """Return a player's most recent match ids."""
        url = f"{self.region_url}/tft/match/v1/matches/by-puuid/{puuid}/ids"
        return self._get(url, params={"start": 0, "count": count}) or []

    def get_match(self, match_id: str) -> dict[str, Any] | None:
        """Return one match's details, or None if it does not exist."""
        return self._get(f"{self.region_url}/tft/match/v1/matches/{match_id}")

    def _get(self, url: str, params: dict[str, int] | None = None) -> Any:
        for attempt in range(MAX_ATTEMPTS):
            backoff_seconds = 2**attempt
            self.limiter.acquire()

            try:
                response = self.session.get(
                    url, params=params, timeout=REQUEST_TIMEOUT_SECONDS
                )
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(backoff_seconds)
                continue

            status = response.status_code
            if status == 200:
                return response.json()
            if status == 404:
                return None
            if status in (401, 403):
                raise RiotApiKeyError("Riot rejected the API key: renew it in .env.")
            if status == 429:
                time.sleep(float(response.headers.get("Retry-After", backoff_seconds)))
            elif status in TEMPORARY_STATUS_CODES:
                time.sleep(backoff_seconds)
            else:
                raise RiotRequestError(f"Unexpected status {status}: {url}")

        raise RiotRequestError(f"Gave up after {MAX_ATTEMPTS} attempts: {url}")
