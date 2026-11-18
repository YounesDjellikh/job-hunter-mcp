"""Filtering and de-duplication applied to every search result."""

from __future__ import annotations

from collections.abc import Iterable

from .sources.base import Job


def _text(job: Job) -> str:
    return f"{job.title} {job.description}".lower()


def apply_filters(
    jobs: Iterable[Job],
    exclude_keywords: Iterable[str] = (),
    min_hourly: float | None = None,
    temp_only: bool = False,
    exclude_employers: Iterable[str] = (),
) -> list[Job]:
    """Drop unwanted jobs and duplicates.

    * exclude_keywords - e.g. "self-employed", "freelance" (to hide self-employed roles)
    * min_hourly       - drops jobs whose *hourly* pay is known and below this; unknown pay is kept
    * temp_only        - drops jobs explicitly marked permanent
    * exclude_employers - employers you already applied to or never want to see
    """
    excl = [k.lower() for k in exclude_keywords if k]
    bad_emp = {e.lower().strip() for e in exclude_employers if e}
    seen: set[tuple[str, str, str]] = set()
    out: list[Job] = []
    for job in jobs:
        text = _text(job)
        if any(k in text for k in excl):
            continue
        if temp_only and job.contract_type == "permanent":
            continue
        if min_hourly is not None and job.salary_period == "hour":
            top = job.salary_max or job.salary_min
            if top is not None and top < min_hourly:
                continue
        if job.employer.lower().strip() in bad_emp:
            continue
        if job.dedupe_key in seen:
            continue
        seen.add(job.dedupe_key)
        out.append(job)
    return out
