# Notes

## Production schedule

The whole pipeline -- SQL Server feature computation *and* the DynamoDB sync --
runs as a single scheduled job:

| | |
|---|---|
| Machine | **Mercedes** |
| Job | **Integrations - OEAdStudentProbability** |
| Schedule | daily at **7:00 AM UTC** |
| Step | **UpdateAndSyncFeatures** (one single step) |

That one step does both of the following, in order:

1. `EXEC [SUP].[ml].[usp_UPDATE_oead_student_features]` -- recomputes/upserts
   `SUP.ml.oead_student_features` (see `SQL/usp_UPDATE_oead_student_features.sql`).
2. `python sync.py` -- reads the rows that just changed and pushes them to the
   `biba_oead_student_features` DynamoDB table.

Deployed code lives at:

```
D:\INTEGRATIONS\OEAd_students_probability_features
```

That deployed folder (not this repo checkout) is what the scheduled job actually
executes -- keep it in sync with this repo when deploying changes (including
`db_credentials.py` and `sync_state.json`, which are gitignored and must exist
there independently, see `doc/recreate-dynamodb.md`). The stored procedure
itself is deployed straight to SQL Server (`SUP` database) and isn't part of
the deployed folder's file set.

---

## Manual / local commands

```powershell
.venv\Scripts\Activate.ps1

python sync.py

python get_dynamodb_item.py S#1000092
```
