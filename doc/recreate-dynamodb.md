# How to Recreate the DynamoDB Table from Scratch

This guide explains how to fully rebuild the `biba_oead_student_features` DynamoDB table
from the beginning of time (earliest records in MSSQL).

---

## When to use this

- Schema change in DynamoDB (e.g., adding a new attribute like `language`).
- Data corruption or accidental deletes in DynamoDB.
- The table needs to reflect hard-deletes that happened in MSSQL (items removed from source
  will persist in DynamoDB during an incremental sync; a full rebuild clears them).

---

## Step 1 — Delete and recreate the DynamoDB table

A full rebuild should start with an empty table so that hard-deleted MSSQL rows do not
linger in DynamoDB. Overwriting in place (skipping this step) is faster but will leave
orphaned items for any student that was deleted from MSSQL since the last full rebuild.

```powershell
# Delete the existing table (waits until deletion completes)
aws dynamodb delete-table --table-name biba_oead_student_features --region us-east-1
aws dynamodb wait table-not-exists --table-name biba_oead_student_features --region us-east-1

# Recreate from the definition file
aws dynamodb create-table --cli-input-json file://infra/create-table.json --region us-east-1
aws dynamodb wait table-exists --table-name biba_oead_student_features --region us-east-1
```

> **Note:** `aws dynamodb wait` polls until the operation completes. Do not proceed to
> the next step until the `wait` command exits.

---

## Step 2 — Reset the sync cursor

Edit `sync_state.json` (or create it if it does not exist) to reset the watermark to the
earliest possible date:

```json
{
  "lastModifiedAt": "2010-01-01T00:00:00.000",
  "lastStudentId": null
}
```

`sync_state.json` is intentionally excluded from version control (`.gitignore`).

---

## Step 3 — Run the sync

```powershell
.venv\Scripts\Activate.ps1
python sync.py
```

The sync reads MSSQL in pages of 20,000 rows ordered by `(modifiedAt, studentId)` and
writes to DynamoDB in batches of 1,000. It saves progress to `sync_state.json` after every
page, so it is safe to interrupt and resume — just re-run `python sync.py` and it will
continue from where it left off.

Depending on total row count, a full rebuild can take several hours. Monitor progress via
the console output, which prints rows processed and elapsed time per batch.

---

## Full rebuild checklist

| # | Action | Command / file |
|---|--------|----------------|
| 1 | Delete DynamoDB table | `aws dynamodb delete-table …` |
| 2 | Wait for deletion | `aws dynamodb wait table-not-exists …` |
| 3 | Recreate DynamoDB table | `aws dynamodb create-table --cli-input-json file://infra/create-table.json …` |
| 4 | Wait for table to be active | `aws dynamodb wait table-exists …` |
| 5 | Reset `sync_state.json` | `{"lastModifiedAt": "2010-01-01T00:00:00.000", "lastStudentId": null}` |
| 6 | Run sync | `python sync.py` |

---

## Alternative: overwrite in place (faster, leaves orphans)

If hard-deleted rows are not a concern (or the table has no deletes), you can skip steps
1–4 and go straight to resetting `sync_state.json` and running `python sync.py`.
`batch_writer` is configured with `overwrite_by_pkeys=["PK"]`, so every MSSQL row will
overwrite the matching DynamoDB item.

---

## db_credentials.py requirements

`sync.py` requires two connection strings in `db_credentials.py`:

```python
# SQL Server — source of oead_student_features
MSSQL_CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=<host>;"
    "Database=SUP;"
    "Uid=<user>;Pwd=<password>;"
    "TrustServerCertificate=yes;"
)

# PostgreSQL — source of public.person (nativelang → language)
PG_CONNECTION_STRING = (
    "Driver={PostgreSQL Unicode};"
    "Server=<host>;"
    "Port=5432;"
    "Database=<database>;"
    "Uid=<user>;Pwd=<password>;"
)
```

The PostgreSQL ODBC driver (`psqlODBC`) must be installed on the machine running the sync.
Download: https://www.postgresql.org/ftp/odbc/versions/msi/
