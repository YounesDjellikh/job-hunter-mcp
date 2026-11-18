"""Reed.co.uk official Jobseeker API.

Free API key: https://www.reed.co.uk/developers/jobseeker
Auth is HTTP Basic with the key as the username and an empty password.
"""

from __future__ import annotations

import httpx

from .base import Job

SEARCH_URL = "https://www.reed.co.uk/api/1.0/search"


def _period(min_sal: float | None) -> str | None:
    # Reed returns annual figures for salaried jobs and hourly figures for most
    # temp work; anything under 200 is almost certainly an hourly rate.
    if min_sal is None:
        return None
    return "hour" if min_sal < 200 else "year"


def search(
    api_key: str,
    keywords: str,
    location: str = "",
    distance_miles: int = 10,
    temp_only: bool = False,
    max_results: int = 25,
    client: httpx.Client | None = None,
) -> list[Job]:
    params: dict[str, object] = {
        "keywords": keywords,
        "distanceFromLocation": distance_miles,
        "resultsToTake": min(max_results, 100),
    }
    if location:
        params["locationName"] = location
    if temp_only:
        params["temp"] = "true"
        params["permanent"] = "false"

    own_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        resp = client.get(SEARCH_URL, params=params, auth=(api_key, ""))
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own_client:
            client.close()

    jobs: list[Job] = []
    for r in data.get("results", []):
        jobs.append(
            Job(
                source="reed",
                source_id=str(r.get("jobId")),
                title=r.get("jobTitle", ""),
                employer=r.get("employerName", ""),
                location=r.get("locationName", ""),
                url=r.get("jobUrl", ""),
                description=r.get("jobDescription", ""),
                salary_min=r.get("minimumSalary"),
                salary_max=r.get("maximumSalary"),
                salary_period=_period(r.get("minimumSalary")),
                contract_type="temporary" if temp_only else None,
                posted=r.get("date"),
            )
        )
    return jobs
