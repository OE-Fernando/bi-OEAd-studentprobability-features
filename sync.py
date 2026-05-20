
import json
from datetime import datetime, timezone

import boto3
import pyodbc

try:
    from db_credentials import MSSQL_CONNECTION_STRING
except ImportError as exc:
    raise RuntimeError(
        "Missing db_credentials.py. Create this file and define MSSQL_CONNECTION_STRING."
    ) from exc


###############################################################################
# CONFIG
###############################################################################

DYNAMODB_TABLE_NAME = "oead_student_features"

AWS_REGION = "us-east-1"

STATE_FILE = "sync_state.json"

MSSQL_PAGE_SIZE = 10000
DYNAMODB_BATCH_SIZE = 1000


###############################################################################
# DYNAMODB CLIENT
###############################################################################

session = boto3.Session(region_name=AWS_REGION)

dynamodb = session.resource("dynamodb")

table = dynamodb.Table(DYNAMODB_TABLE_NAME)


###############################################################################
# STATE MANAGEMENT
###############################################################################


def load_last_sync_timestamp():
    """
    Load last successful sync timestamp.
    """

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            return state["lastModifiedAt"]

    except FileNotFoundError:
        return "2010-01-01T00:00:00.000"



def save_last_sync_timestamp(timestamp_str):
    """
    Persist successful sync watermark.
    """

    with open(STATE_FILE, "w") as f:
        json.dump(
            {
                "lastModifiedAt": timestamp_str
            },
            f,
            indent=2
        )


###############################################################################
# MSSQL READ
###############################################################################


def fetch_updated_rows(last_sync_timestamp, page_size=MSSQL_PAGE_SIZE):
    """
    Yield MSSQL rows updated since the last sync in pages.
    """

    sql = """
    SELECT
          PK
        , studentId
        , active_level
        , enrollment
        , country_iso
        , Is_B2B__c
        , gender
        , ageGroup
        , studentHistory
        , createdAt
        , modifiedAt

    FROM [SUP].[ml].[oead_student_features]

    WHERE modifiedAt > ?

    ORDER BY modifiedAt ASC
    """

    conn = pyodbc.connect(MSSQL_CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(sql, last_sync_timestamp)

    columns = [column[0] for column in cursor.description]

    while True:
        rows = cursor.fetchmany(page_size)
        if not rows:
            break

        yield [dict(zip(columns, row)) for row in rows]

    cursor.close()
    conn.close()


###############################################################################
# HELPERS
###############################################################################


def datetime_to_iso(dt):
    """
    Convert datetime to UTC ISO8601.
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).isoformat()



def datetime_to_epoch(dt):
    """
    Convert datetime to epoch seconds.
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return int(dt.timestamp())


###############################################################################
# DYNAMODB ITEM MAPPING
###############################################################################


def build_dynamodb_item(row):
    """
    Transform MSSQL row into DynamoDB item.
    """

    modified_at_iso = datetime_to_iso(row["modifiedAt"])

    item = {
        "PK": row["PK"],

        "studentId": row["studentId"],

        "active_level": row["active_level"],
        "enrollment": row["enrollment"],
        "country_iso": row["country_iso"],
        "Is_B2B__c": row["Is_B2B__c"],
        "gender": row["gender"],
        "ageGroup": row["ageGroup"],
        "studentHistory": row["studentHistory"],

        "createdAt": datetime_to_iso(row["createdAt"]),

        "modifiedAt": modified_at_iso,

        "modifiedAtEpoch": datetime_to_epoch(row["modifiedAt"]),

        "GSI1PK": "FEATURE"
    }

    return {
        k: v
        for k, v in item.items()
        if v is not None
    }


###############################################################################
# BATCH WRITE
###############################################################################


def write_batch(batch_rows):
    """
    Write batch to DynamoDB.

    Uses batch_writer which automatically:
    - retries unprocessed items
    - buffers requests
    - handles throughput errors
    """

    with table.batch_writer(overwrite_by_pkeys=["PK"]) as batch:

        for row in batch_rows:

            item = build_dynamodb_item(row)

            batch.put_item(Item=item)

    return len(batch_rows)


###############################################################################
# CHUNKING
###############################################################################


def chunked(data, chunk_size):
    """
    Yield chunks.
    """

    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


###############################################################################
# MAIN SYNC
###############################################################################


def run_sync():

    sync_started = datetime.utcnow()

    print("Loading last sync state...")
    last_sync_timestamp = load_last_sync_timestamp()
    print(f"Last sync timestamp: {last_sync_timestamp}")

    print("Reading MSSQL updated rows in pages...")

    processed = 0
    max_modified_at = None

    for page_number, rows_page in enumerate(
        fetch_updated_rows(last_sync_timestamp), start=1
    ):
        page_size = len(rows_page)
        print(f"Read page {page_number} with {page_size} rows from MSSQL")

        if page_size == 0:
            continue

        for batch_number, batch_rows in enumerate(
            chunked(rows_page, DYNAMODB_BATCH_SIZE), start=1
        ):
            count = write_batch(batch_rows)
            processed += count

            for row in batch_rows:
                row_modified_at = row["modifiedAt"]
                if max_modified_at is None or row_modified_at > max_modified_at:
                    max_modified_at = row_modified_at

            print(
                f"Processed page {page_number}, batch {batch_number}: "
                f"{processed} rows total"
            )

    if processed == 0:
        print("Nothing to sync.")
        return

    if max_modified_at is not None:
        save_last_sync_timestamp(
            max_modified_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        )

    elapsed = datetime.utcnow() - sync_started

    print("Sync completed.")
    print(f"Rows synced: {processed}")
    print(f"Elapsed seconds: {elapsed.total_seconds():.2f}")


###############################################################################
# ENTRYPOINT
###############################################################################

if __name__ == "__main__":
    run_sync()
