# Notes

## Production schedule

`sync.py` runs in production on server **Mercedes**, as the job:

> **Integrations - OEAdStudentProbability**

Scheduled to run **daily at 7:00 AM UTC**.

Deployed code lives at:

```
D:\INTEGRATIONS\OEAd_students_probability_features
```

That deployed folder (not this repo checkout) is what the scheduled job actually
executes -- keep it in sync with this repo when deploying changes (including
`db_credentials.py` and `sync_state.json`, which are gitignored and must exist
there independently, see `doc/recreate-dynamodb.md`).

---

## Manual / local commands

```powershell
.venv\Scripts\Activate.ps1

python sync.py

python get_dynamodb_item.py S#1000092
```
