import httpx
import pytest

from job_hunter_mcp import countries, filters, gmail
from job_hunter_mcp.config import load_config
from job_hunter_mcp.sources import adzuna
from job_hunter_mcp.sources.base import Job


# ---------------- email classification in European languages ----------------

@pytest.mark.parametrize("lang, subject, body, expected", [
    # French
    ("fr", "Votre candidature", "Malheureusement, nous ne pouvons pas donner une suite favorable à votre candidature.", "rejection"),
    ("fr", "Candidature - Préparateur de commandes", "Votre candidature n'a pas été retenue.", "rejection"),
    ("fr", "Convocation à un entretien", "Nous souhaitons vous inviter à un entretien.", "next_step"),
    ("fr", "Accusé de réception", "Nous avons bien reçu votre candidature.", "acknowledgement"),
    ("fr", "Prêt approuvé !", "Votre prêt approuvé de 3000 €", "scam"),
    # German
    ("de", "Ihre Bewerbung", "Leider müssen wir Ihnen mitteilen, dass wir uns für einen anderen Bewerber entschieden haben.", "rejection"),
    ("de", "Einladung zum Vorstellungsgespräch", "Wir laden Sie gerne ein.", "next_step"),
    ("de", "Eingangsbestätigung", "Vielen Dank für Ihre Bewerbung.", "acknowledgement"),
    # Spanish
    ("es", "Tu candidatura", "Lamentablemente no has sido seleccionado para el puesto.", "rejection"),
    ("es", "Entrevista", "Nos gustaría invitarte a una entrevista.", "next_step"),
    ("es", "Candidatura recibida", "Hemos recibido tu candidatura.", "acknowledgement"),
    # Italian
    ("it", "La tua candidatura", "Purtroppo abbiamo deciso di proseguire con altri candidati.", "rejection"),
    ("it", "Invito a colloquio", "Saremmo lieti di incontrarti per un colloquio.", "next_step"),
    ("it", "Grazie", "Abbiamo ricevuto la tua candidatura.", "acknowledgement"),
    # Dutch
    ("nl", "Je sollicitatie", "Helaas hebben we besloten je niet uit te nodigen.", "rejection"),
    ("nl", "Uitnodiging sollicitatiegesprek", "Graag nodigen we je uit.", "next_step"),
    ("nl", "Ontvangstbevestiging", "Bedankt voor je sollicitatie.", "acknowledgement"),
    # Polish
    ("pl", "Twoja aplikacja", "Niestety zdecydowaliśmy się na innego kandydata.", "rejection"),
    ("pl", "Zaproszenie na rozmowę kwalifikacyjną", "Zapraszamy na rozmowę kwalifikacyjną.", "next_step"),
    # Portuguese
    ("pt", "A sua candidatura", "Infelizmente não foi selecionado.", "rejection"),
    # A job ad mentioning a permanent contract must NOT be read as a job offer
    ("de", "Neue Stellenangebote für Sie", "Lagerhelfer (m/w/d) - unbefristeter Arbeitsvertrag", "job_related"),
])
def test_classify_multilingual(lang, subject, body, expected):
    assert gmail.classify(subject, body) == expected, lang


# ---------------- countries ----------------

def test_country_normalise_and_currency():
    assert countries.normalise("UK") == "gb"
    assert countries.normalise("FR") == "fr"
    assert countries.currency("de") == "EUR" and countries.currency("pl") == "PLN"
    assert countries.sources_for("gb") == ("reed", "adzuna")
    assert countries.sources_for("fr") == ("adzuna",)
    with pytest.raises(ValueError):
        countries.normalise("us")


def test_adzuna_uses_country_and_km():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"results": [{"id": "1", "title": "Préparateur de commandes",
                                                      "company": {"display_name": "Logistique SA"},
                                                      "location": {"display_name": "Lyon"},
                                                      "redirect_url": "https://adz/1", "salary_min": 12.0}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    jobs = adzuna.search("id", "key", "préparateur", "Lyon", country="fr", distance_km=20, client=client)
    assert "/jobs/fr/search/" in seen["url"] and "distance=20" in seen["url"]
    assert jobs[0].country == "fr" and jobs[0].currency == "EUR" and jobs[0].salary_period == "hour"


# ---------------- filters ----------------

@pytest.mark.parametrize("title", [
    "Livreur auto-entrepreneur", "Kurier selbstständig", "Repartidor autónomo",
    "Consulente con partita IVA", "Bezorger ZZP", "Kurier - samozatrudnienie",
])
def test_default_filters_drop_self_employed_in_all_languages(title):
    j = Job(source="t", source_id="1", title=title, employer="X", location="Y", url="u")
    assert filters.apply_filters([j], countries.SELF_EMPLOYED_KEYWORDS) == []


# ---------------- config ----------------

def test_config_country_and_legacy_key(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path))
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("data_dir: %s\nsearch:\n  country: FR\n  location: Lyon\n  distance_km: 25\n" % tmp_path)
    cfg = load_config(cfg_file)
    assert cfg.search.country == "fr" and cfg.search.distance_km == 25
    cfg_file.write_text("data_dir: %s\nadzuna_country: de\n" % tmp_path)
    assert load_config(cfg_file).search.country == "de"
