from pathlib import Path

import httpx
import openpyxl
import pytest

from job_hunter_mcp import filters, gmail
from job_hunter_mcp.sources import adzuna, reed
from job_hunter_mcp.sources.base import Job
from job_hunter_mcp.tracker import Tracker


def job(title="Warehouse Operative", employer="Acme", location="Manchester", **kw):
    return Job(source="test", source_id=title, title=title, employer=employer, location=location, url="u", **kw)


# ---------------- filters ----------------

def test_filters_drop_excluded_keywords_and_duplicates():
    jobs = [job(), job(), job(title="Self-employed courier"), job(title="Picker", employer="Beta")]
    out = filters.apply_filters(jobs, exclude_keywords=["self-employed"])
    assert [j.title for j in out] == ["Warehouse Operative", "Picker"]


def test_filters_min_hourly_keeps_unknown_pay():
    jobs = [
        job(title="Low", salary_min=11.0, salary_max=11.5, salary_period="hour"),
        job(title="Good", salary_min=13.0, salary_max=15.0, salary_period="hour"),
        job(title="Unknown"),
        job(title="Annual", salary_min=25000, salary_period="year"),
    ]
    out = [j.title for j in filters.apply_filters(jobs, min_hourly=12.5)]
    assert out == ["Good", "Unknown", "Annual"]


def test_filters_temp_only_and_employer_exclusion():
    jobs = [job(title="A", contract_type="permanent"), job(title="B", contract_type="temporary"),
            job(title="C", employer="Already Applied Ltd")]
    out = filters.apply_filters(jobs, temp_only=True, exclude_employers=["already applied ltd"])
    assert [j.title for j in out] == ["B"]


# ---------------- tracker ----------------

def test_tracker_add_update_list_and_export(tmp_path: Path):
    t = Tracker(tmp_path / "t.db")
    a = t.add("Acme Foods", "Production Operative", status="applied", url="https://example.com/1")
    b = t.add("Northwind Staffing", "Warehouse Nights", status="saved")
    t.update(b.id, status="applied", note="texted recruiter")
    t.update(a.id, status="rejected", note="email: unfortunately")
    assert t.get(b.id).status == "applied" and "texted recruiter" in t.get(b.id).notes
    assert t.summary()["rejected"] == 1 and t.summary()["total"] == 2
    # rejected sorts after applied
    assert [x.employer for x in t.list()] == ["Northwind Staffing", "Acme Foods"]

    out = t.export_excel(tmp_path / "tracker.xlsx")
    ws = openpyxl.load_workbook(out)["Applications"]
    assert ws.cell(2, 2).value == "APPLIED"
    assert ws.cell(3, 2).value == "REJECTED"
    # hyperlink sits on the row it belongs to
    assert ws.cell(3, 7).hyperlink.target == "https://example.com/1"
    assert ws.cell(2, 7).hyperlink is None


def test_tracker_rejects_bad_status(tmp_path: Path):
    t = Tracker(tmp_path / "t.db")
    with pytest.raises(ValueError):
        t.add("X", "Y", status="maybe")


# ---------------- gmail classification ----------------

@pytest.mark.parametrize("subject, body, expected", [
    ("Your application for Customer Advisor", "we won't be moving forward with your application", "rejection"),
    ("An update on your application", "We regret to inform you that we shall not be progressing", "rejection"),
    ("Invitation to complete an online assessment", "next stage", "next_step"),
    ("Invitation to take on a few tasks", "Congratulations on making it through the screening phase", "next_step"),
    ("Thank you for applying", "We have received your application", "acknowledgement"),
    ("Loan approved instantly", "Transfer £3,000 directly to you bank account", "scam"),
    ("Appointment Booked", "Your appointment has been scheduled", "offer"),
    ("Black Friday sale", "50% off shoes", "other"),
])
def test_classify(subject, body, expected):
    assert gmail.classify(subject, body) == expected


def test_match_applications(tmp_path: Path):
    t = Tracker(tmp_path / "t.db")
    a = t.add("Contoso Post (Fabrikam)", "Mail Sorter")
    t.add("Tailspin Pubs", "Kitchen Porter")
    ids = gmail.match_applications("hr@fabrikamstaffing.example", "Fabrikam registration", "", t.list())
    assert ids == [a.id]


# ---------------- sources (mocked HTTP) ----------------

def _client(payload):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))


def test_reed_parsing():
    payload = {"results": [{"jobId": 1, "jobTitle": "Picker", "employerName": "Acme", "locationName": "Manchester",
                            "jobUrl": "https://reed/1", "minimumSalary": 12.8, "maximumSalary": 13.5}]}
    jobs = reed.search("k", "picker", "Manchester", temp_only=True, client=_client(payload))
    assert jobs[0].employer == "Acme" and jobs[0].salary_period == "hour" and jobs[0].contract_type == "temporary"


def test_adzuna_parsing():
    payload = {"results": [{"id": "9", "title": "Cleaner", "company": {"display_name": "Clean Co"},
                            "location": {"display_name": "Leeds"}, "redirect_url": "https://adz/9",
                            "salary_min": 24000, "contract_type": "permanent"}]}
    jobs = adzuna.search("id", "key", "cleaner", "Leeds", client=_client(payload))
    assert jobs[0].contract_type == "permanent" and jobs[0].salary_period == "year"
