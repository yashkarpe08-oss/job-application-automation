import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))
import tracker  # noqa: E402


@pytest.fixture
def wb_path(tmp_path):
    return tmp_path / "apps.xlsx"


def run(wb_path, capsys, *argv):
    tracker.main(["--path", str(wb_path), *argv])
    return capsys.readouterr().out


def test_add_and_dedupe(wb_path, capsys):
    out = json.loads(run(wb_path, capsys, "add", "--company", "Acme", "--role", "Audit Associate",
                         "--url", "https://www.indeed.com/viewjob?jk=1"))
    assert out == {"duplicate": False, "id": 1}
    # Same URL with different scheme/trailing slash is a duplicate
    out = json.loads(run(wb_path, capsys, "add", "--company", "Acme Ltd", "--role", "Other",
                         "--url", "http://indeed.com/viewjob?jk=1/"))
    assert out["duplicate"] is True and out["id"] == 1
    # Same company+role, different case, is a duplicate
    out = json.loads(run(wb_path, capsys, "add", "--company", "ACME", "--role", "audit  associate"))
    assert out["duplicate"] is True
    out = json.loads(run(wb_path, capsys, "add", "--company", "Beta", "--role", "AP Clerk"))
    assert out["id"] == 2


def test_applied_sets_dates_and_due(wb_path, capsys):
    run(wb_path, capsys, "add", "--company", "Acme", "--role", "Analyst")
    row = json.loads(run(wb_path, capsys, "update", "1", "--status", "Applied", "--fit", "4.2"))
    assert row["Date Applied"] == date.today().isoformat()
    assert row["Follow-up Due"] == (date.today() + timedelta(days=7)).isoformat()
    assert row["Fit Score"] == 4.2
    assert "Found -> Applied" in row["Notes"]
    # Backdated application is overdue
    run(wb_path, capsys, "add", "--company", "Old", "--role", "Clerk", "--status", "Applied",
        "--applied", (date.today() - timedelta(days=10)).isoformat())
    due = json.loads(run(wb_path, capsys, "due"))
    assert [d["Company"] for d in due] == ["Old"]
    assert due[0]["Days Overdue"] == 3
    # Rejection clears the follow-up date
    row = json.loads(run(wb_path, capsys, "update", "2", "--status", "Rejected"))
    assert row["Follow-up Due"] is None


def test_validation(wb_path, capsys):
    run(wb_path, capsys, "add", "--company", "Acme", "--role", "Analyst")
    with pytest.raises(SystemExit):
        run(wb_path, capsys, "update", "1", "--fit", "9")
    with pytest.raises(SystemExit):
        run(wb_path, capsys, "update", "99", "--note", "x")


def test_workbook_structure(wb_path, capsys):
    run(wb_path, capsys, "init")
    wb = load_workbook(wb_path)
    assert wb.sheetnames == ["Applications", "Dashboard"]
    ws = wb["Applications"]
    assert [c.value for c in ws[1]] == tracker.HEADERS
    assert ws.data_validations.dataValidation
    assert str(wb["Dashboard"]["B4"].value).startswith("=COUNTIF(")
