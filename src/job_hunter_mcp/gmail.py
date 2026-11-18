"""Read-only Gmail check: find replies to your applications and classify them.

Uses the official Gmail API with the read-only scope. You create your own OAuth
client in Google Cloud (see README); the token stays on your machine.
Nothing is ever sent, deleted or modified.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Order matters: the first category whose pattern matches wins.
# Patterns cover English, French, German, Spanish, Italian, Dutch, Polish and Portuguese.
# Recruiters word things creatively - if a real email slips through, add its phrase here (and a test).
RULES: list[tuple[str, list[str]]] = [
    ("scam", [
        # en
        r"\bloan (approved|for christmas)\b", r"pre-?approved loan", r"£\s?3,?000 .*minutes",
        r"money in minutes", r"transfer £[\d,]+ directly",
        # fr / de / es / it / nl / pl / pt
        r"prêt (approuvé|accordé|pré-?approuvé)", r"kredit (genehmigt|bewilligt|zugesagt)",
        r"préstamo (aprobado|preaprobado)", r"prestito (approvato|pre-?approvato)",
        r"lening (goedgekeurd|toegekend)", r"pożyczk\w* (zatwierdzon|przyznan)", r"empréstimo aprovado",
    ]),
    ("rejection", [
        # en
        r"unfortunately", r"not be progressing", r"not progressing", r"won[’']?t be (moving|progressing)",
        r"will not be (moving|progressing|taking)", r"not been successful", r"unsuccessful",
        r"regret to inform", r"other candidates", r"not been selected", r"not selected",
        r"position has been filled", r"decided not to proceed", r"no longer (recruiting|considering)",
        # fr
        r"malheureusement", r"ne (pouvons|pourrons) pas donner (une suite )?favorable", r"pas (pu )?donner suite",
        r"(n['’]a|n['’]avons) pas (été )?retenu", r"candidature n['’]a pas été retenue", r"nous regrettons",
        r"autres? candidat",
        # de
        r"\bleider\b", r"\babsage\b", r"nicht (weiter )?berücksichtig", r"für (eine[n]?|einen anderen) (anderen )?(bewerber|kandidat)",
        r"nicht in die engere wahl",
        # es
        r"lamentablemente", r"desafortunadamente", r"lamentamos (informarte|informarle|comunicarte)",
        r"no (has|ha) sido seleccionad", r"otros? candidat", r"no continuar(emos)? con tu candidatura",
        # it
        r"purtroppo", r"siamo spiacenti", r"non (è|e') stat[ao] selezionat", r"altri candidati",
        r"non (potremo|possiamo) procedere",
        # nl
        r"\bhelaas\b", r"afgewezen", r"niet (verder )?(meenemen|door)", r"andere kandida",
        # pl
        r"\bniestety\b", r"nie (zakwalifikował|została? wybran)", r"odrzucon", r"inn(ego|ych) kandydat",
        # pt
        r"infelizmente", r"não foi selecionad", r"outros candidatos",
    ]),
    ("offer", [
        # en
        r"\bjob offer\b", r"pleased to offer", r"offer of employment", r"your start date",
        r"induction (is|has been) (booked|confirmed)", r"appointment (is|has been) (scheduled|confirmed)",
        # fr / de / es / it / nl / pl / pt
        r"promesse d['’]embauche", r"proposition d['’]embauche", r"votre date de (début|démarrage|prise de poste)",
        r"\bstellenzusage\b", r"\bzusage\b", r"ihr (erster arbeitstag|eintrittsdatum)",
        r"carta de oferta", r"nos complace ofrecerte", r"fecha de incorporación",
        r"lettera di (offerta|assunzione)", r"siamo lieti di offrirti",
        r"we bieden je graag",
        r"z przyjemnością (oferujemy|proponujemy)",
        r"temos o prazer de oferecer",
    ]),
    ("next_step", [
        # en
        r"invite you to", r"invitation to", r"interview", r"assessment centre", r"online assessment",
        r"next stage", r"shortlisted", r"screening (questions|phase)", r"take on a few tasks",
        r"finish (the|your) application", r"complete your (outstanding|application|documents)",
        # fr
        r"entretien", r"convocation", r"(vous )?inviter? à", r"prochaine étape", r"test en ligne", r"présélectionn",
        # de
        r"vorstellungsgespräch", r"einladung", r"nächste[nr]? (runde|schritt|phase)", r"online-?test",
        r"kennenlerngespräch",
        # es
        r"entrevista", r"invitación", r"siguiente (fase|paso)", r"prueba en línea", r"preseleccionad",
        # it
        r"colloquio", r"\binvito\b", r"prossima fase", r"test online", r"preselezionat",
        # nl
        r"sollicitatiegesprek", r"uitnodiging", r"volgende (ronde|stap)", r"kennismakingsgesprek",
        # pl
        r"rozmow[aęy] kwalifikacyjn", r"zaproszenie", r"kolejn(y|ego) etap",
        # pt
        r"convite", r"próxima (fase|etapa)",
    ]),
    ("acknowledgement", [
        # en
        r"received your application", r"thank you for (applying|your application)", r"application (sent|submitted)",
        r"we['’]ve sent your application", r"application acknowledg",
        # fr
        r"(bien )?reçu votre candidature", r"merci (pour|de) votre candidature", r"accusé de réception",
        # de
        r"(vielen )?dank für ihre bewerbung", r"bewerbung (ist )?(bei uns )?eingegangen", r"eingangsbestätigung",
        # es
        r"hemos recibido (tu|su) (candidatura|solicitud)", r"gracias por (tu|su) (candidatura|solicitud)",
        # it
        r"abbiamo ricevuto la (tua|sua) candidatura", r"grazie per (la tua|la sua|aver inviato la) candidatura",
        # nl
        r"(bedankt|dank) voor (je|uw) sollicitatie", r"ontvangstbevestiging", r"sollicitatie (goed )?ontvangen",
        # pl
        r"dziękujemy za (przesłanie )?(twoj|pan|zgłoszeni|aplikacj)", r"otrzymaliśmy (twoj|pana|pani)?\w* ?(aplikacj|zgłoszeni|cv)",
        # pt
        r"recebemos a sua candidatura", r"obrigad[oa] pela sua candidatura",
    ]),
]

JOB_HINTS = re.compile(
    r"application|applied|vacanc|recruit|candidate|role|position|job|interview|assessment|onboarding|shift"
    r"|candidature|recrutement|poste|emploi"            # fr
    r"|bewerbung|stelle|stellenangebot"        # de
    r"|candidatura|empleo|vacante|puesto|lavoro"       # es / it
    r"|sollicitatie|vacature"                          # nl
    r"|rekrutac|aplikacj|praca|ofert"                  # pl
    r"|vaga",                                          # pt
    re.I,
)


@dataclass
class EmailItem:
    id: str
    date: str
    sender: str
    subject: str
    snippet: str
    category: str
    matched_application_ids: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


def classify(subject: str, body: str) -> str:
    text = f"{subject}\n{body}".lower()
    for category, patterns in RULES:
        if any(re.search(p, text) for p in patterns):
            return category
    return "job_related" if JOB_HINTS.search(text) else "other"


def match_applications(sender: str, subject: str, body: str, applications) -> list[int]:
    """Return ids of tracked applications whose employer name appears in the email."""
    hay = f"{sender} {subject} {body}".lower()
    ids = []
    for a in applications:
        name = a.employer.lower()
        # Match on the full name or its first distinctive word ("Acme Foods (Northwind)" -> "acme foods", "northwind").
        parts = [name] + [p.strip(" ()-") for p in re.split(r"[()\-–,]", name) if len(p.strip(" ()-")) > 3]
        if any(p and p in hay for p in parts):
            ids.append(a.id)
    return ids


def _service(credentials_path: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Gmail support is not installed. Run: pip install 'job-hunter-mcp[gmail]'") from e

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise RuntimeError(
                    f"Gmail credentials not found at {credentials_path}. See README > 'Gmail setup'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def fetch_recent(credentials_path: Path, token_path: Path, days: int = 2, max_messages: int = 100) -> list[dict]:
    """Return recent messages (all folders except spam/trash) as dicts with id/date/sender/subject/snippet."""
    svc = _service(credentials_path, token_path)
    query = f"newer_than:{int(days)}d -category:promotions -category:social"
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_messages).execute()
    out = []
    for m in resp.get("messages", []):
        msg = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        out.append({
            "id": m["id"],
            "date": headers.get("date", ""),
            "sender": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "snippet": msg.get("snippet", ""),
        })
    return out


def check_inbox(messages: list[dict], applications) -> list[EmailItem]:
    items = []
    for m in messages:
        cat = classify(m["subject"], m["snippet"])
        if cat == "other":
            continue
        items.append(EmailItem(
            id=m["id"], date=m["date"], sender=m["sender"], subject=m["subject"], snippet=m["snippet"][:300],
            category=cat, matched_application_ids=match_applications(m["sender"], m["subject"], m["snippet"], applications),
        ))
    return items
