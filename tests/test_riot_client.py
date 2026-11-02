"""RiotClient retry rules, tested with a fake session instead of the real API."""

import pytest

from tft_meta.collector import riot_client
from tft_meta.collector.riot_client import RiotApiKeyError, RiotClient, RiotRequestError
from tft_meta.config import Settings


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}

    def json(self):
        return self.body


class FakeSession:
    """Returns the given responses in order and counts the calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture
def sleeps(monkeypatch):
    """Record sleeps instead of waiting, so tests run instantly."""
    recorded = []
    monkeypatch.setattr(riot_client.time, "sleep", recorded.append)
    return recorded


def make_client(responses):
    client = RiotClient(Settings(riot_api_key="test-key", database_url="unused"))
    client.session = FakeSession(responses)
    return client


def test_success_returns_json(sleeps):
    client = make_client([FakeResponse(200, {"match_id": "TEST_1"})])
    assert client.get_match("TEST_1") == {"match_id": "TEST_1"}


def test_missing_match_returns_none(sleeps):
    assert make_client([FakeResponse(404)]).get_match("TEST_1") is None


def test_rejected_key_is_not_retried(sleeps):
    client = make_client([FakeResponse(401)])
    with pytest.raises(RiotApiKeyError):
        client.get_match("TEST_1")
    assert client.session.calls == 1


def test_rate_limit_waits_for_retry_after(sleeps):
    client = make_client([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, [])])
    assert client.get_match_ids("puuid") == []
    assert sleeps == [7.0]


def test_server_errors_back_off_exponentially(sleeps):
    client = make_client([FakeResponse(503), FakeResponse(503), FakeResponse(200, {})])
    client.get_match("TEST_1")
    assert sleeps == [1, 2]


def test_gives_up_after_max_attempts(sleeps):
    client = make_client([FakeResponse(500)] * riot_client.MAX_ATTEMPTS)
    with pytest.raises(RiotRequestError):
        client.get_match("TEST_1")
    assert client.session.calls == riot_client.MAX_ATTEMPTS
