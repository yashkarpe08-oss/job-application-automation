---
description: Add or update a job in the Excel tracker from plain English, e.g. "/track applied to Deloitte audit associate today"
argument-hint: "<what happened>"
---

Update the job tracker for: $ARGUMENTS

1. Find the job with `python tracker/tracker.py list` or `find`. If it is not there and I gave a company and role, add it with `add`.
2. Make the change with `python tracker/tracker.py update <id> ...` (status, dates, contact, note).
3. If I pasted a job posting or URL for a new job, add it and then use the `job-evaluator` agent on it.
4. Show the updated row in one line.
