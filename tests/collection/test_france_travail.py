import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from nextrole.collection import CollectionError, FranceTravailClient, FranceTravailSearch

FIXED_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def load_fixture(name: str) -> dict[str, object]:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "france_travail" / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_client_collects_paginated_offers_and_maps_source_fields() -> None:
    requested_ranges: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            assert b"client_secret=test-secret" in request.content
            return httpx.Response(200, json={"access_token": "test-token"})

        assert request.headers["Authorization"] == "Bearer test-token"
        requested_range = request.url.params["range"]
        requested_ranges.append(requested_range)
        fixture_name = "search_page_1.json" if requested_range == "0-1" else "search_page_2.json"
        return httpx.Response(206, json=load_fixture(fixture_name))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = FranceTravailClient(
        "test-client",
        "test-secret",
        http_client=http_client,
        clock=lambda: FIXED_NOW,
    )

    batch = client.collect(FranceTravailSearch(keywords="data", max_results=3, page_size=2))

    assert requested_ranges == ["0-1", "2-2"]
    assert len(batch.pages) == 2
    assert len(batch.postings) == 3
    assert batch.postings[0].source_job_id == "198ABCD"
    assert batch.postings[0].company_name == "Example Analytics"
    assert str(batch.postings[1].source_url).endswith("/198EFGH")
    assert batch.collected_at == FIXED_NOW


def test_client_retries_transient_responses_using_retry_after() -> None:
    search_attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal search_attempts
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-token"})
        search_attempts += 1
        if search_attempts == 1:
            return httpx.Response(503, headers={"Retry-After": "0.25"})
        return httpx.Response(206, json={"resultats": []})

    client = FranceTravailClient(
        "test-client",
        "test-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=delays.append,
    )

    batch = client.collect(FranceTravailSearch(keywords="python", max_results=1))

    assert search_attempts == 2
    assert delays == [0.25]
    assert batch.postings == ()


def test_client_fails_after_bounded_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = FranceTravailClient(
        "test-client",
        "test-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=1,
        retry_backoff_seconds=0,
        sleep=lambda _: None,
    )

    with pytest.raises(CollectionError, match="remained unavailable after 2 attempts"):
        client.collect(FranceTravailSearch(keywords="sql"))


def test_client_rejects_invalid_offer_shapes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-token"})
        return httpx.Response(200, json={"resultats": ["not-an-object"]})

    client = FranceTravailClient(
        "test-client",
        "test-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(CollectionError, match="non-object offer"):
        client.collect(FranceTravailSearch(keywords="sql", max_results=1))


def test_client_requires_credentials() -> None:
    with pytest.raises(ValueError, match="credentials are required"):
        FranceTravailClient("", "")
