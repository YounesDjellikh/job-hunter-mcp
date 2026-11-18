"""Common job model shared by every source."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    employer: str
    location: str
    url: str
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    # "hour", "year" or None when the board does not say.
    salary_period: str | None = None
    contract_type: str | None = None  # "temporary", "permanent", "contract"
    posted: str | None = None
    country: str = "gb"
    currency: str = "GBP"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["description"] = (self.description or "")[:400]
        return d

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        norm = lambda s: " ".join((s or "").lower().split())
        return (norm(self.employer), norm(self.title), norm(self.location))
