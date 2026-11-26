#!/usr/bin/env python3
"""Excel job-application tracker.

Every agent in this repo reads and writes the tracker through this script,
so the spreadsheet stays consistent. Run `python tracker/tracker.py -h`.

The workbook has two sheets:
  Applications  one row per job, with a Status dropdown and colour coding
  Dashboard     live counts per status, built from Excel formulas
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = Path(os.environ.get("TRACKER_PATH", ROOT / "data" / "applications.xlsx"))

COLUMNS = [
    ("ID", 7),
    ("Date Found", 12),
    ("Company", 24),
    ("Role", 32),
    ("Location", 16),
    ("Source", 11),
    ("URL", 40),
    ("Fit Score", 9),
    ("Status", 15),
    ("Date Applied", 12),
    ("Follow-up Due", 13),
    ("Last Contact", 12),
    ("Contact", 20),
    ("CV File", 28),
    ("Cover Letter", 28),
    ("Report", 28),
    ("Notes", 50),
]
HEADERS = [c[0] for c in COLUMNS]
COL = {name: i + 1 for i, name in enumerate(HEADERS)}

# Status -> fill colour. Order is the pipeline order used on the Dashboard.
STATUSES = {
    "Found": "EDEDED",
    "Evaluated": "DDEBF7",
    "Ready to Apply": "FFF2CC",
    "Applied": "BDD7EE",
    "Follow-up Sent": "C9C9F0",
    "Interview": "C6EFCE",
    "Offer": "70C17A",
    "Rejected": "F4B6B6",
    "Skipped": "D9D9D9",
    "Withdrawn": "D9D9D9",
    "Ghosted": "E7D3C1",
}
ACTIVE = {"Applied", "Follow-up Sent", "Interview"}
DATE_FIELDS = {"Date Found", "Date Applied", "Follow-up Due", "Last Contact"}
FOLLOW_UP_DAYS = int(os.environ.get("FOLLOW_UP_DAYS", "7"))
MAX_ROWS = 2000  # extent of dropdown / formatting ranges

# CLI flag -> column
FIELD_FLAGS = {
    "company": "Company",
    "role": "Role",
    "location": "Location",
    "source": "Source",
    "url": "URL",
    "fit": "Fit Score",
    "status": "Status",
    "applied": "Date Applied",
    "followup": "Follow-up Due",
    "last_contact": "Last Contact",
    "contact": "Contact",
    "cv": "CV File",
    "cover": "Cover Letter",
    "report": "Report",
}


# ---------------------------------------------------------------- workbook

def create_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(HEADERS)
    header_fill = PatternFill("solid", fgColor="1F3864")
    for i, (name, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "D2"
    last_col = get_column_letter(len(HEADERS))
    ws.auto_filter.ref = f"A1:{last_col}{MAX_ROWS}"

    status_col = get_column_letter(COL["Status"])
    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(STATUSES) + '"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Unknown status",
        error="Pick a status from the list.",
    )
    ws.add_data_validation(dv)
    dv.add(f"{status_col}2:{status_col}{MAX_ROWS}")

    fit_col = get_column_letter(COL["Fit Score"])
    fit_dv = DataValidation(type="decimal", operator="between", formula1="0", formula2="5", allow_blank=True)
    ws.add_data_validation(fit_dv)
    fit_dv.add(f"{fit_col}2:{fit_col}{MAX_ROWS}")

    rng = f"A2:{last_col}{MAX_ROWS}"
    for status, colour in STATUSES.items():
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'${status_col}2="{status}"'], fill=PatternFill("solid", fgColor=colour)),
        )
    # Overdue follow-up: bold red date when due date has passed on an active application.
    due_col = get_column_letter(COL["Follow-up Due"])
    ws.conditional_formatting.add(
        f"{due_col}2:{due_col}{MAX_ROWS}",
        FormulaRule(
            formula=[f'AND({due_col}2<>"",{due_col}2<=TODAY(),OR(${status_col}2="Applied",${status_col}2="Follow-up Sent"))'],
            font=Font(bold=True, color="C00000"),
        ),
    )

    dash = wb.create_sheet("Dashboard")
    dash["A1"] = "Job search dashboard"
    dash["A1"].font = Font(bold=True, size=14)
    dash["A3"], dash["B3"] = "Status", "Count"
    for c in ("A3", "B3"):
        dash[c].font = Font(bold=True, color="FFFFFF")
        dash[c].fill = header_fill
    rng_status = f"Applications!${status_col}$2:${status_col}${MAX_ROWS}"
    row = 4
    for status, colour in STATUSES.items():
        dash.cell(row=row, column=1, value=status).fill = PatternFill("solid", fgColor=colour)
        dash.cell(row=row, column=2, value=f'=COUNTIF({rng_status},"{status}")')
        row += 1
    dash.cell(row=row, column=1, value="Total").font = Font(bold=True)
    dash.cell(row=row, column=2, value=f"=SUM(B4:B{row - 1})").font = Font(bold=True)
    row += 2
    applied_like = '"Applied","Follow-up Sent","Interview","Offer","Rejected","Ghosted"'
    dash.cell(row=row, column=1, value="Applications sent")
    dash.cell(row=row, column=2, value=f"=SUMPRODUCT(COUNTIF({rng_status},{{{applied_like}}}))")
    sent_row = row
    row += 1
    dash.cell(row=row, column=1, value="Interview rate")
    dash.cell(
        row=row, column=2,
        value=f'=IFERROR((COUNTIF({rng_status},"Interview")+COUNTIF({rng_status},"Offer"))/B{sent_row},0)',
    ).number_format = "0%"
    row += 1
    dash.cell(row=row, column=1, value="Follow-ups overdue")
    dash.cell(
        row=row, column=2,
        value=(f"=COUNTIFS(Applications!${due_col}$2:${due_col}${MAX_ROWS},\"<=\"&TODAY(),{rng_status},\"Applied\")"
               f"+COUNTIFS(Applications!${due_col}$2:${due_col}${MAX_ROWS},\"<=\"&TODAY(),{rng_status},\"Follow-up Sent\")"),
    )
    row += 1
    fit_rng = f"Applications!${fit_col}$2:${fit_col}${MAX_ROWS}"
    dash.cell(row=row, column=1, value="Average fit score")
    dash.cell(row=row, column=2, value=f"=IFERROR(AVERAGE({fit_rng}),0)").number_format = "0.0"
    dash.column_dimensions["A"].width = 22
    dash.column_dimensions["B"].width = 10

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def open_sheet(path: Path):
    if not path.exists():
        create_workbook(path)
    wb = load_workbook(path)
    return wb, wb["Applications"]


def parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().lower()
    if text == "today":
        return date.today()
    return datetime.strptime(text, "%Y-%m-%d").date()


def row_to_dict(ws, r: int) -> dict:
    out = {}
    for name in HEADERS:
        v = ws.cell(row=r, column=COL[name]).value
        if isinstance(v, (datetime, date)):
            v = parse_date(v).isoformat()
        out[name] = v
    return out


def data_rows(ws):
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=COL["ID"]).value is not None:
            yield r


def find_row(ws, job_id: int):
    for r in data_rows(ws):
        if int(ws.cell(row=r, column=COL["ID"]).value) == job_id:
            return r
    return None


def norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def norm_url(u) -> str:
    u = norm(u).split("#")[0].rstrip("/")
    for p in ("https://", "http://", "www."):
        if u.startswith(p):
            u = u[len(p):]
    return u


def find_duplicate(ws, url=None, company=None, role=None):
    for r in data_rows(ws):
        row_url = ws.cell(row=r, column=COL["URL"]).value
        if url and row_url and norm_url(row_url) == norm_url(url):
            return r
        if company and role and norm(ws.cell(row=r, column=COL["Company"]).value) == norm(company) \
                and norm(ws.cell(row=r, column=COL["Role"]).value) == norm(role):
            return r
    return None


def set_cell(ws, r: int, name: str, value) -> None:
    if name == "Status" and value not in STATUSES:
        raise SystemExit(f"Unknown status '{value}'. Use one of: {', '.join(STATUSES)}")
    if name == "Fit Score" and value not in (None, ""):
        value = float(value)
        if not 0 <= value <= 5:
            raise SystemExit("Fit score must be between 0 and 5.")
    cell = ws.cell(row=r, column=COL[name])
    if name in DATE_FIELDS:
        value = parse_date(value)
        cell.number_format = "yyyy-mm-dd"
    cell.value = value
    if name == "URL" and value:
        cell.hyperlink = value
        cell.font = Font(color="0563C1", underline="single")


def append_note(ws, r: int, note: str) -> None:
    cell = ws.cell(row=r, column=COL["Notes"])
    stamped = f"[{date.today().isoformat()}] {note}"
    cell.value = f"{cell.value}\n{stamped}" if cell.value else stamped
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def apply_status_side_effects(ws, r: int, status: str, explicit: dict) -> None:
    """Fill the dates a status change implies, unless the caller set them."""
    today = date.today()
    if status == "Applied":
        if "Date Applied" not in explicit and not ws.cell(row=r, column=COL["Date Applied"]).value:
            set_cell(ws, r, "Date Applied", today)
        if "Follow-up Due" not in explicit:
            applied = parse_date(ws.cell(row=r, column=COL["Date Applied"]).value) or today
            set_cell(ws, r, "Follow-up Due", applied + timedelta(days=FOLLOW_UP_DAYS))
    elif status == "Follow-up Sent":
        if "Last Contact" not in explicit:
            set_cell(ws, r, "Last Contact", today)
        if "Follow-up Due" not in explicit:
            set_cell(ws, r, "Follow-up Due", today + timedelta(days=FOLLOW_UP_DAYS))
    elif status not in ACTIVE and "Follow-up Due" not in explicit:
        ws.cell(row=r, column=COL["Follow-up Due"]).value = None


# ---------------------------------------------------------------- commands

def collect_fields(args) -> dict:
    fields = {}
    for flag, col in FIELD_FLAGS.items():
        v = getattr(args, flag, None)
        if v is not None:
            fields[col] = v
    return fields


def cmd_init(args):
    if args.path.exists() and not args.force:
        print(f"Tracker already exists at {args.path} (use --force to recreate it).")
        return
    create_workbook(args.path)
    print(f"Created {args.path}")


def cmd_add(args):
    wb, ws = open_sheet(args.path)
    dup = find_duplicate(ws, args.url, args.company, args.role)
    if dup:
        existing = row_to_dict(ws, dup)
        print(json.dumps({"duplicate": True, "id": existing["ID"], "status": existing["Status"]}))
        return
    ids = [int(ws.cell(row=r, column=COL["ID"]).value) for r in data_rows(ws)]
    new_id = max(ids, default=0) + 1
    r = max(list(data_rows(ws)), default=1) + 1
    ws.cell(row=r, column=COL["ID"], value=new_id)
    set_cell(ws, r, "Date Found", date.today())
    fields = collect_fields(args)
    fields.setdefault("Status", "Found")
    for col, v in fields.items():
        set_cell(ws, r, col, v)
    apply_status_side_effects(ws, r, fields["Status"], fields)
    if args.note:
        append_note(ws, r, args.note)
    wb.save(args.path)
    print(json.dumps({"duplicate": False, "id": new_id}))


def cmd_update(args):
    wb, ws = open_sheet(args.path)
    r = find_row(ws, args.id)
    if r is None:
        raise SystemExit(f"No application with ID {args.id}")
    fields = collect_fields(args)
    old_status = ws.cell(row=r, column=COL["Status"]).value
    for col, v in fields.items():
        set_cell(ws, r, col, v)
    if "Status" in fields and fields["Status"] != old_status:
        apply_status_side_effects(ws, r, fields["Status"], fields)
        append_note(ws, r, f"Status: {old_status} -> {fields['Status']}")
    if args.note:
        append_note(ws, r, args.note)
    wb.save(args.path)
    print(json.dumps(row_to_dict(ws, r), default=str))


def cmd_get(args):
    _, ws = open_sheet(args.path)
    r = find_row(ws, args.id)
    if r is None:
        raise SystemExit(f"No application with ID {args.id}")
    print(json.dumps(row_to_dict(ws, r), indent=2, default=str))


def cmd_find(args):
    _, ws = open_sheet(args.path)
    r = find_duplicate(ws, args.url, args.company, args.role)
    print(json.dumps(row_to_dict(ws, r) if r else None, default=str))


def cmd_list(args):
    _, ws = open_sheet(args.path)
    rows = [row_to_dict(ws, r) for r in data_rows(ws)]
    if args.status:
        wanted = set(args.status)
        rows = [x for x in rows if x["Status"] in wanted]
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        print("No applications.")
        return
    for x in rows:
        fit = x["Fit Score"] if x["Fit Score"] is not None else "-"
        print(f"#{x['ID']:<4} {x['Status']:<15} fit {fit:<4} {x['Company']} | {x['Role']}")


def cmd_due(args):
    _, ws = open_sheet(args.path)
    today = date.today()
    out = []
    for r in data_rows(ws):
        x = row_to_dict(ws, r)
        due = parse_date(x["Follow-up Due"])
        if x["Status"] in ("Applied", "Follow-up Sent") and due and due <= today:
            x["Days Overdue"] = (today - due).days
            out.append(x)
    print(json.dumps(out, indent=2, default=str))


def cmd_stats(args):
    _, ws = open_sheet(args.path)
    counts = {s: 0 for s in STATUSES}
    for r in data_rows(ws):
        s = ws.cell(row=r, column=COL["Status"]).value
        counts[s] = counts.get(s, 0) + 1
    print(json.dumps({k: v for k, v in counts.items() if v}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Job application tracker (Excel)")
    p.add_argument("--path", type=Path, default=DEFAULT_PATH, help="Workbook path (default data/applications.xlsx)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="Create the workbook")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    def field_args(sp, require_core=False):
        sp.add_argument("--company", required=require_core)
        sp.add_argument("--role", required=require_core)
        sp.add_argument("--location")
        sp.add_argument("--source", help="Indeed, LinkedIn, Company site, Recruiter, Referral...")
        sp.add_argument("--url")
        sp.add_argument("--fit", type=float, help="Fit score 0-5")
        sp.add_argument("--status", choices=list(STATUSES))
        sp.add_argument("--applied", help="Date applied, YYYY-MM-DD or 'today'")
        sp.add_argument("--followup", help="Follow-up due date, YYYY-MM-DD")
        sp.add_argument("--last-contact", dest="last_contact", help="YYYY-MM-DD or 'today'")
        sp.add_argument("--contact", help="Recruiter / hiring manager name")
        sp.add_argument("--cv", help="Path of the tailored CV")
        sp.add_argument("--cover", help="Path of the cover letter")
        sp.add_argument("--report", help="Path of the evaluation report")
        sp.add_argument("--note", help="Appended to Notes with today's date")

    s = sub.add_parser("add", help="Add a job (skips duplicates by URL or company+role)")
    field_args(s, require_core=True)
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("update", help="Update a job by ID")
    s.add_argument("id", type=int)
    field_args(s)
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("get", help="Show one job as JSON")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("find", help="Look up a job by URL or company+role")
    s.add_argument("--url")
    s.add_argument("--company")
    s.add_argument("--role")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("list", help="List jobs")
    s.add_argument("--status", nargs="*", choices=list(STATUSES))
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("due", help="Active applications whose follow-up is due")
    s.set_defaults(func=cmd_due)

    s = sub.add_parser("stats", help="Counts per status")
    s.set_defaults(func=cmd_stats)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
