"""Country support.

Adzuna covers these European markets with one API. Reed is UK-only.
"""

from __future__ import annotations

# code: (name, currency, sources available)
COUNTRIES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "gb": ("United Kingdom", "GBP", ("reed", "adzuna")),
    "fr": ("France", "EUR", ("adzuna",)),
    "de": ("Germany", "EUR", ("adzuna",)),
    "es": ("Spain", "EUR", ("adzuna",)),
    "it": ("Italy", "EUR", ("adzuna",)),
    "nl": ("Netherlands", "EUR", ("adzuna",)),
    "be": ("Belgium", "EUR", ("adzuna",)),
    "at": ("Austria", "EUR", ("adzuna",)),
    "ch": ("Switzerland", "CHF", ("adzuna",)),
    "pl": ("Poland", "PLN", ("adzuna",)),
}

ALIASES = {"uk": "gb", "england": "gb", "scotland": "gb", "wales": "gb"}


def normalise(code: str | None) -> str:
    c = (code or "gb").lower().strip()
    c = ALIASES.get(c, c)
    if c not in COUNTRIES:
        raise ValueError(f"Unsupported country '{code}'. Supported: {', '.join(sorted(COUNTRIES))}")
    return c


def currency(code: str) -> str:
    return COUNTRIES[normalise(code)][1]


def sources_for(code: str) -> tuple[str, ...]:
    return COUNTRIES[normalise(code)][2]


# Words that signal self-employment / freelance / commission-only work, in each
# supported language. Hidden by default; override exclude_keywords in config.yaml to see them.
SELF_EMPLOYED_KEYWORDS: list[str] = [
    # English
    "self-employed", "self employed", "freelance", "commission only", "commission-only",
    # French
    "auto-entrepreneur", "autoentrepreneur", "micro-entrepreneur", "indépendant", "commission uniquement",
    # German
    "selbstständig", "selbststandig", "freiberufler", "freiberuflich", "provisionsbasis", "nur provision",
    # Spanish
    "autónomo", "autonomo", "solo comisión", "solo comision",
    # Italian
    "partita iva", "libero professionista", "solo provvigioni",
    # Dutch
    "zzp", "zelfstandige", "zelfstandig ondernemer", "alleen provisie",
    # Polish
    "samozatrudnienie", "działalność gospodarcza", "dzialalnosc gospodarcza", "tylko prowizja",
]
