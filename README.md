# job-application-automation

Claude Code agents that automate the busywork of a job search, with every
application tracked in an Excel workbook.

| Agent | What it does | Tracker status it sets |
|---|---|---|
| `job-scout` | Searches Indeed (and other Irish job boards) using `config/search.yml`, drops duplicates and misfits | Found |
| `job-evaluator` | Scores fit 0-5, writes an honest report with gaps and keywords to `reports/` | Ready to Apply / Skipped |
| `application-writer` | Tailored 2-page CV and 1-page cover letter as PDFs in `output/`, checked against a checklist | (files recorded) |
| `follow-up-tracker` | Reads Gmail replies to update statuses; drafts follow-ups for overdue applications as Gmail drafts | Interview / Rejected / Offer |

The agents never submit applications or send email. You do that, then mark the job Applied.

## Use

In Claude Code, in this folder:

- `/job-hunt` runs everything and ends with a "Needs you" list
- `/job-hunt scout`, `/job-hunt evaluate`, `/job-hunt write`, `/job-hunt followup` run one step
- `/track applied to Acme audit associate today` updates the tracker in plain English

The tracker is `data/applications.xlsx`: an **Applications** sheet (status dropdown,
colour per status, overdue follow-ups in red, filters) and a **Dashboard** sheet
(counts per status, applications sent, interview rate, overdue follow-ups, average fit).

```bash
pip install -r requirements.txt
python tracker/tracker.py init
python tracker/tracker.py add --company "Acme" --role "Audit Associate" --url "https://..."
python tracker/tracker.py update 1 --status Applied
python tracker/tracker.py due
python tracker/tracker.py list
```

## Setup
1. `pip install -r requirements.txt`
2. Optional: copy `profile/profile.example.md` to `profile/profile.md` and fill it in.
3. Edit `config/search.yml` for roles, towns and exclusions.
4. Connect the Indeed and Gmail connectors in Claude so the scout and follow-up agents can use them.

## Privacy
This repo is public, so `.gitignore` keeps the tracker, profile, reports and CVs out of git.
To keep them between cloud sessions, make the repository private and remove those lines.
