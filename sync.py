
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

DYNAMODB_TABLE_NAME = "biba_oead_student_features"

AWS_REGION = "us-east-1"

STATE_FILE = "sync_state.json"

MSSQL_PAGE_SIZE = 20000
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


def load_last_sync_state():
    """
    Load last successful sync cursor (modifiedAt + studentId).
    """

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            return state["lastModifiedAt"], state.get("lastStudentId")

    except FileNotFoundError:
        return "2010-01-01T00:00:00.000", None



def save_last_sync_state(timestamp_str, student_id):
    """
    Persist successful sync watermark.
    """

    with open(STATE_FILE, "w") as f:
        json.dump(
            {
                "lastModifiedAt": timestamp_str,
                "lastStudentId": student_id,
            },
            f,
            indent=2
        )


###############################################################################
# MSSQL READ
###############################################################################


def fetch_updated_rows(last_modified_at, last_student_id, page_size=MSSQL_PAGE_SIZE):
    """
    Yield MSSQL rows updated since the last sync in pages.
    Uses a composite (modifiedAt, studentId) cursor to handle ties.
    """

    if last_student_id is None:
        print(f"Query filter: modifiedAt > '{last_modified_at}'")
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
            , language
            , max_pc_reservations
            , createdAt
            , modifiedAt

        FROM [SUP].[ml].[oead_student_features] WITH (NOLOCK)

        WHERE modifiedAt > ?

        ORDER BY modifiedAt ASC, studentId ASC
        """
        params = (last_modified_at,)
    else:
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
            , language
            , max_pc_reservations
            , createdAt
            , modifiedAt

        FROM [SUP].[ml].[oead_student_features] WITH (NOLOCK)

        WHERE (modifiedAt > ?) OR (modifiedAt = ? AND studentId > ?)

        ORDER BY modifiedAt ASC, studentId ASC
        """
        print(f"Query filter: modifiedAt > '{last_modified_at}' OR (modifiedAt = '{last_modified_at}' AND studentId > {last_student_id})")
        params = (last_modified_at, last_modified_at, last_student_id)

    conn = pyodbc.connect(MSSQL_CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(sql, params)

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
        "language": row["language"],
        "max_pc_reservations": row["max_pc_reservations"],

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

    sync_started = datetime.now(timezone.utc)

    print("Loading last sync state...")
    last_modified_at, last_student_id = load_last_sync_state()
    print(f"Last sync cursor: modifiedAt={last_modified_at}, studentId={last_student_id}")

    print("Reading MSSQL updated rows in pages...")

    processed = 0

    for page_number, rows_page in enumerate(
        fetch_updated_rows(last_modified_at, last_student_id), start=1
    ):
        page_size = len(rows_page)
        last_row_in_page = rows_page[-1] if rows_page else None
        page_last_modified_at = last_row_in_page["modifiedAt"] if last_row_in_page else None
        page_last_student_id = last_row_in_page["studentId"] if last_row_in_page else None
        print(
            f"Read page {page_number} with {page_size} rows from MSSQL"
            f" | fetch cursor: modifiedAt='{last_modified_at}', studentId={last_student_id}"
            f" | page last: modifiedAt='{page_last_modified_at}', studentId={page_last_student_id}"
        )

        if page_size == 0:
            continue

        for batch_number, batch_rows in enumerate(
            chunked(rows_page, DYNAMODB_BATCH_SIZE), start=1
        ):
            count = write_batch(batch_rows)
            processed += count

            print(
                f"Processed page {page_number}, batch {batch_number}: "
                f"{processed} rows total"
            )

        last_modified_at = page_last_modified_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        last_student_id = page_last_student_id
        save_last_sync_state(last_modified_at, last_student_id)
        print(f"State saved: modifiedAt='{last_modified_at}', studentId={last_student_id}")

    if processed == 0:
        print("Nothing to sync.")
        return

    elapsed = datetime.now(timezone.utc) - sync_started

    print("Sync completed.")
    print(f"Rows synced: {processed}")
    print(f"Elapsed seconds: {elapsed.total_seconds():.2f}")


###############################################################################
# ENTRYPOINT
###############################################################################

if __name__ == "__main__":
    run_sync()
