---
description: Run the full job pipeline - check replies, scout, evaluate, prepare applications - and report what needs you
argument-hint: "[scout|evaluate|write|followup] (optional: run one step only)"
---

Run the job application pipeline. If `$ARGUMENTS` names one step, run only that step.

0. If `data/applications.xlsx` does not exist, run `python tracker/tracker.py init`.
Indeed rate-limits the account, so the steps that use it (scout, evaluate) run one after the other, never in parallel. If the tracker has no Applied, Follow-up Sent or Interview rows, skip step 1.

1. **followup**: use the `follow-up-tracker` agent to read Gmail replies, update statuses and draft overdue follow-ups.
2. **scout**: use the `job-scout` agent to find and log new postings.
3. **evaluate**: run `python tracker/tracker.py list --status Found --json`. Give all the IDs to ONE `job-evaluator` agent, earliest closing date first. Do not run evaluators in parallel: they share the Indeed rate limit and block each other.
4. **write**: run `python tracker/tracker.py list --status "Ready to Apply" --json`. For jobs with an empty "CV File", ask me which ones to prepare before starting the `application-writer` agent, unless I said "write all".
5. Finish with:
   - `python tracker/tracker.py stats`
   - a short "Needs you" list: documents ready to submit (with URLs), Gmail drafts to send, interviews to schedule
   - a reminder to mark submitted applications with `python tracker/tracker.py update <id> --status Applied`

Never submit an application or send an email yourself.
