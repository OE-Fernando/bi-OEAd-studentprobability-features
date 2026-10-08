# BI-8174 Implementation Steps

Adds `n_pc_reserved_45` and `n_pc_attended_45` (count of PC/private-class
reservations and attended classes in the trailing 45 days) to the student
feature pipeline. All scripts/code changes are already written in this repo
(this PR) -- this document is the manual run order to deploy them.

Ticket: https://openenglish.jira.com/browse/BI-8174
Epic: https://openenglish.jira.com/browse/BI-8173

## Why these two tables, and why `-1` as a sentinel

STEP 4 of `usp_UPDATE_oead_student_features` already computes
`qtyReserved`/`qtyConfirmed` per student over the trailing 45 days -- it just
discards them after collapsing into the `studentHistory` bucket string. These
two new fields expose those same raw counts as their own columns, on both
`oead_student_history` (where STEP 4/5 computes them) and
`oead_student_features` (the table synced to DynamoDB), the same place
`studentHistory` itself lives on both tables.

Unlike `max_pc_reservations` (where real values start at 1, so `0` was free
to use as a "this was never set" comparison sentinel), **`0` is a legitimate
real value** for these two counts -- a student can genuinely have zero PC
reservations/attendance in 45 days. So every change-detection comparison
below uses `-1` instead, matching the convention already used in this proc's
STEP 3 MERGE for an analogous integer column.

## Prerequisites

Run these in order. Each SQL step is non-destructive and idempotent (safe to
re-run) except the backfill, which is also safe to re-run (it only updates
rows whose computed value differs from what's stored).

### Step 1 -- Alter `SUP.ml.oead_student_history`

Run:

```
SQL/oead_student_history_ALTER_ADD_pc_45day_counts.sql
```

Adds `n_pc_reserved_45` and `n_pc_attended_45` (both `INT NULL`) to
`oead_student_history`. No existing rows are touched.

> Note: this repo has no `CREATE_TBL.sql` schema snapshot for
> `oead_student_history` (unlike `oead_student_features`). Consider
> generating one via SSMS "Script Table as > CREATE To" and adding it to
> `SQL/` while you're making this change, so the gap doesn't widen further.

### Step 2 -- Alter `SUP.ml.oead_student_features`

Run:

```
SQL/oead_student_features_ALTER_ADD_pc_45day_counts.sql
```

Adds the same two columns to `oead_student_features`. No existing rows are
touched. (`SQL/oead_student_features_CREATE_TBL.sql`'s schema snapshot has
already been updated to match, for documentation only -- do not run that
file against the live table, see the warning at its top.)

### Step 3 -- Deploy the updated stored procedure

Deploy `SQL/usp_UPDATE_oead_student_features.sql` (an `ALTER PROCEDURE`, no
data loss). From this point on, its normal daily run computes and maintains
both new columns for any student it reprocesses (those with
`DWH.dim_student.start_time > @lastStartTimeUtc`). It does not touch
existing rows outside that window on its own -- that's what Step 4 is for.

### Step 4 -- One-time backfill

Run:

```
SQL/oead_student_features_BACKFILL_pc_45day_counts.sql
```

This does two things, in order:
1. Backfills `oead_student_history` directly from
   `LK.dbo.oead_reservations_attendance` (same 45-day window STEP 4 uses).
2. Backfills `oead_student_features` from the now-updated
   `oead_student_history` (same source STEP 6 of the proc reads from).

Both updates only bump `modifiedAt` for rows whose computed value actually
changed -- that's what queues a row for the next `sync.py` run. No
`sync_state.json` watermark reset needed, no DynamoDB table rebuild needed.

Each `UPDATE` prints a `PRINT 'backfill complete. Rows updated: N'` line --
check both counts look reasonable before moving on.

### Step 5 -- Deploy the updated `sync.py`

`sync.py`'s `fetch_updated_rows()` SELECTs and `build_dynamodb_item()` now
include `n_pc_reserved_45` / `n_pc_attended_45`. Deploy it to
`D:\INTEGRATIONS\OEAd_students_probability_features` on **Mercedes** (see
`doc/notes.md` for the production job details), replacing the existing
deployed copy.

Deploy this **before** the next 7:00 AM UTC run of
`Integrations - OEAdStudentProbability` / `UpdateAndSyncFeatures`, since that
single job step runs the proc then `sync.py` back-to-back -- or trigger a
manual `python sync.py` run yourself once steps 1-4 are done, using the
existing `sync_state.json` cursor (no reset required).

## Verification

After Step 5 (or the next scheduled run), spot-check the DynamoDB item for a
student known to have recent PC activity, the same way we verified
`max_pc_reservations`:

```powershell
.venv\Scripts\python.exe get_dynamodb_item.py S#<studentId>
```

Confirm `n_pc_reserved_45` and `n_pc_attended_45` are present with sane
values (and that `n_pc_attended_45 <= n_pc_reserved_45` for that student).

## Out of scope for this document (separate follow-up)

The consumer repo, `bi-OEAd-studentprobability`, does not yet read these two
new attributes -- `StudentService._DEFAULT_FEATURES`/`_normalize`, the
`student_cols` lists in `data_srv_lambda.py`/`data_contracts_lambda.py`, and
the training-data export (`export_training_data.py`,
`merge_into_DWH_table.sql`) all need their own changes if/when the
probability model is meant to train on or serve these new features. That's
separate work, not covered by BI-8174's scope as currently ticketed.
