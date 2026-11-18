"""Application tracker: SQLite storage + colour-coded Excel export.

The Excel file is regenerated from the database on every export, so links, colours
and row order are always correct (editing an existing workbook in place tends to leave
hyperlinks and merged cells pointing at the wrong rows).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

STATUSES = ("saved", "applied", "viewed", "interview", "offer", "rejected", "withdrawn")

# Fill colour and font colour per status.
STATUS_STYLE = {
    "saved": ("DDEBF7", "1F4E79"),      # blue  - not applied yet
    "applied": ("E2EFDA", "375623"),    # green - applied
    "viewed": ("E2EFDA", "C65911"),     # green, orange text - employer viewed it
    "interview": ("C6EFCE", "006100"),  # strong green
    "offer": ("A9D08E", "006100"),
    "rejected": ("F8CBAD", "C00000"),   # red
    "withdrawn": ("D9D9D9", "595959"),  # grey
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer TEXT NOT NULL,
    role TEXT NOT NULL,
    location TEXT DEFAULT '',
    pay TEXT DEFAULT '',
    url TEXT DEFAULT '',
    source TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'saved',
    applied_on TEXT DEFAULT '',
    updated_on TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
"""


@dataclass
class Application:
    id: int
    employer: str
    role: str
    location: str
    pay: str
    url: str
    source: str
    status: str
    applied_on: str
    updated_on: str
    notes: str


class Tracker:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c:
            c.executescript(SCHEMA)
            c.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- writes -------------------------------------------------------
    def add(
        self,
        employer: str,
        role: str,
        status: str = "applied",
        location: str = "",
        pay: str = "",
        url: str = "",
        source: str = "",
        notes: str = "",
    ) -> Application:
        status = _check_status(status)
        today = date.today().isoformat()
        with closing(self._conn()) as c:
            cur = c.execute(
                "INSERT INTO applications (employer, role, location, pay, url, source, status, applied_on, updated_on, notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (employer, role, location, pay, url, source, status,
                 today if status != "saved" else "", today, notes),
            )
            c.commit()
            return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def update(self, app_id: int, status: str | None = None, note: str | None = None) -> Application:
        app = self.get(app_id)
        if app is None:
            raise ValueError(f"No application with id {app_id}")
        today = date.today().isoformat()
        new_status = _check_status(status) if status else app.status
        notes = app.notes
        if note:
            notes = f"[{today}] {note}" + (f"\n{notes}" if notes else "")
        applied_on = app.applied_on or (today if new_status != "saved" else "")
        with closing(self._conn()) as c:
            c.execute(
                "UPDATE applications SET status=?, notes=?, applied_on=?, updated_on=? WHERE id=?",
                (new_status, notes, applied_on, today, app_id),
            )
            c.commit()
        return self.get(app_id)  # type: ignore[return-value]

    def delete(self, app_id: int) -> bool:
        with closing(self._conn()) as c:
            cur = c.execute("DELETE FROM applications WHERE id=?", (app_id,))
            c.commit()
            return cur.rowcount > 0

    # ---- reads --------------------------------------------------------
    def get(self, app_id: int) -> Application | None:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
        return Application(**dict(row)) if row else None

    def list(self, status: str | None = None) -> list[Application]:
        q, args = "SELECT * FROM applications", ()
        if status:
            q += " WHERE status=?"
            args = (_check_status(status),)
        q += " ORDER BY CASE status WHEN 'offer' THEN 0 WHEN 'interview' THEN 1 WHEN 'viewed' THEN 2"
        q += " WHEN 'applied' THEN 3 WHEN 'saved' THEN 4 WHEN 'rejected' THEN 5 ELSE 6 END, id"
        with closing(self._conn()) as c:
            return [Application(**dict(r)) for r in c.execute(q, args).fetchall()]

    def find_by_employer(self, name: str) -> list[Application]:
        name = name.lower().strip()
        return [a for a in self.list() if name and (name in a.employer.lower() or a.employer.lower() in name)]

    def summary(self) -> dict[str, int]:
        counts = {s: 0 for s in STATUSES}
        for a in self.list():
            counts[a.status] = counts.get(a.status, 0) + 1
        counts["total"] = sum(v for k, v in counts.items() if k != "total")
        return counts

    # ---- export -------------------------------------------------------
    def export_excel(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "Applications"
        headers = ["#", "Status", "Employer", "Role", "Location", "Pay", "Link", "Applied", "Updated", "Source", "Notes"]
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            cell = ws.cell(1, col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", start_color="305496", end_color="305496")
            cell.alignment = Alignment(vertical="center")

        for i, a in enumerate(self.list(), start=1):
            ws.append([i, a.status.upper(), a.employer, a.role, a.location, a.pay, "Open" if a.url else "",
                       a.applied_on, a.updated_on, a.source, a.notes])
            r = ws.max_row
            fill, font_colour = STATUS_STYLE.get(a.status, ("FFFFFF", "000000"))
            for col in range(1, len(headers) + 1):
                ws.cell(r, col).fill = PatternFill("solid", start_color=fill, end_color=fill)
                ws.cell(r, col).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(r, 2).font = Font(bold=True, color=font_colour)
            if a.url:
                ws.cell(r, 7).hyperlink = a.url
                ws.cell(r, 7).font = Font(color="0563C1", underline="single")

        widths = [5, 12, 26, 34, 22, 18, 8, 12, 12, 10, 60]
        for col, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # Summary sheet
        s = wb.create_sheet("Summary")
        s.append(["Status", "Count"])
        for k, v in self.summary().items():
            s.append([k, v])
        s.column_dimensions["A"].width = 14
        wb.save(path)
        return path


def _check_status(status: str) -> str:
    s = (status or "").lower().strip()
    if s not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    return s
