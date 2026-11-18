"""Adzuna official job search API.

Free app id/key: https://developer.adzuna.com/
One API for the UK and most of Europe (fr, de, es, it, nl, be, at, ch, pl), with
structured contract_type / contract_time fields.
"""

from __future__ import annotations

import httpx

from ..countries import currency, normalise
from .base import Job

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"
MILES_TO_KM = 1.609


def search(
    app_id: str,
    app_key: str,
    keywords: str,
    location: str = "",
    distance_miles: int = 10,
    temp_only: bool = False,
    max_results: int = 25,
    country: str = "gb",
    client: httpx.Client | None = None,
    distance_km: int | None = None,
) -> list[Job]:
    country = normalise(country)
    params: dict[str, object] = {
        "app_id": app_id,
        "app_key": app_key,
        "what": keywords,
        "results_per_page": min(max_results, 50),
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
        params["distance"] = distance_km if distance_km is not None else round(distance_miles * MILES_TO_KM)
    if temp_only:
        params["contract_type"] = "contract"

    own_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        resp = client.get(SEARCH_URL.format(country=country), params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own_client:
            client.close()

    jobs: list[Job] = []
    for r in data.get("results", []):
        sal_min = r.get("salary_min")
        jobs.append(
            Job(
                source="adzuna",
                source_id=str(r.get("id")),
                title=r.get("title", ""),
                employer=(r.get("company") or {}).get("display_name", ""),
                location=(r.get("location") or {}).get("display_name", ""),
                url=r.get("redirect_url", ""),
                description=r.get("description", ""),
                salary_min=sal_min,
                salary_max=r.get("salary_max"),
                salary_period=("hour" if sal_min and sal_min < 200 else "year") if sal_min else None,
                contract_type={"contract": "temporary", "permanent": "permanent"}.get(r.get("contract_type") or ""),
                posted=r.get("created"),
                country=country,
                currency=currency(country),
            )
        )
    return jobs
