"""Client for the official France Travail job-offers API."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from nextrole.domain import RawJobPosting

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SEARCH_SCOPE = "api_offresdemploiv2 o2dsoffre"
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class CollectionError(RuntimeError):
    """Raised when a source response cannot be safely collected or mapped."""


class FranceTravailSearch(BaseModel):
    """Bounded search configuration for one collection run."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    keywords: str = Field(min_length=1)
    max_results: int = Field(default=150, ge=1, le=3_000)
    page_size: int = Field(default=150, ge=1, le=150)


@dataclass(frozen=True)
class CollectionBatch:
    source: str
    collected_at: datetime
    query: FranceTravailSearch
    pages: tuple[dict[str, Any], ...]
    postings: tuple[RawJobPosting, ...]


class FranceTravailClient:
    """Authenticated, paginated connector with bounded transient retries."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("France Travail client credentials are required")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._client_id = client_id
        self._client_secret = client_secret
        self._client = http_client or httpx.Client(timeout=30.0)
        self._owns_client = http_client is None
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep
        self._clock = clock or (lambda: datetime.now(UTC))
        self._access_token: str | None = None

    def __enter__(self) -> FranceTravailClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def collect(self, query: FranceTravailSearch) -> CollectionBatch:
        collected_at = self._clock()
        pages: list[dict[str, Any]] = []
        postings: list[RawJobPosting] = []

        for start in range(0, query.max_results, query.page_size):
            requested_count = min(query.page_size, query.max_results - start)
            end = start + requested_count - 1
            response = self._request(
                "GET",
                SEARCH_URL,
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
                params={"motsCles": query.keywords, "range": f"{start}-{end}"},
            )
            page = self._json_object(response)
            pages.append(page)

            offers = page.get("resultats", [])
            if not isinstance(offers, list):
                raise CollectionError("France Travail response field 'resultats' is not a list")

            postings.extend(self._map_offer(offer, collected_at) for offer in offers)
            if len(offers) < requested_count:
                break

        return CollectionBatch(
            source="france_travail",
            collected_at=collected_at,
            query=query,
            pages=tuple(pages),
            postings=tuple(postings[: query.max_results]),
        )

    def _get_access_token(self) -> str:
        if self._access_token is not None:
            return self._access_token

        response = self._request(
            "POST",
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": SEARCH_SCOPE,
            },
        )
        payload = self._json_object(response)
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise CollectionError("France Travail token response has no access_token")
        self._access_token = access_token
        return access_token

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as error:
                if attempt == self._max_retries:
                    raise CollectionError(f"request to France Travail failed: {error}") from error
                self._sleep(self._retry_delay(attempt, None))
                continue

            if response.status_code not in RETRIABLE_STATUS_CODES:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    raise CollectionError(
                        f"France Travail returned HTTP {response.status_code}"
                    ) from error
                return response

            if attempt == self._max_retries:
                raise CollectionError(
                    f"France Travail remained unavailable after {attempt + 1} attempts"
                )
            self._sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))

        raise AssertionError("retry loop exited unexpectedly")

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return float(min(max(float(retry_after), 0.0), 30.0))
            except ValueError:
                pass
        return float(self._retry_backoff_seconds * (2**attempt))

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise CollectionError("France Travail returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise CollectionError("France Travail returned a non-object JSON response")
        return payload

    @staticmethod
    def _map_offer(offer: object, collected_at: datetime) -> RawJobPosting:
        if not isinstance(offer, dict):
            raise CollectionError("France Travail returned a non-object offer")

        source_job_id = offer.get("id")
        source_url = _nested_value(offer, "origineOffre", "urlOrigine")
        if not source_url and isinstance(source_job_id, str):
            source_url = (
                "https://candidat.francetravail.fr/offres/recherche/detail/" + source_job_id
            )

        try:
            return RawJobPosting.model_validate(
                {
                    "source": "france_travail",
                    "source_job_id": source_job_id,
                    "title": offer.get("intitule"),
                    "description": offer.get("description"),
                    "source_url": source_url,
                    "company_name": _nested_value(offer, "entreprise", "nom"),
                    "location_text": _nested_value(offer, "lieuTravail", "libelle"),
                    "published_at": offer.get("dateCreation"),
                    "collected_at": collected_at,
                    "contract_text": offer.get("typeContratLibelle"),
                    "salary_text": _nested_value(offer, "salaire", "libelle"),
                    "remote_text": offer.get("teletravail"),
                    "payload": offer,
                }
            )
        except ValueError as error:
            offer_id = source_job_id if isinstance(source_job_id, str) else "unknown"
            raise CollectionError(f"invalid France Travail offer {offer_id}: {error}") from error


def _nested_value(payload: dict[str, Any], parent: str, child: str) -> Any:
    nested = payload.get(parent)
    return nested.get(child) if isinstance(nested, dict) else None
