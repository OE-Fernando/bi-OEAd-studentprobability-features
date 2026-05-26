import argparse
import json
import time

import boto3
from botocore.exceptions import ClientError


DYNAMODB_TABLE_NAME = "biba_oead_student_features"
AWS_REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def get_items_by_pks(pk_values):
    """
    Fetch multiple DynamoDB items by PK using batch_get_item.
    Returns (items, elapsed_seconds).
    """

    keys = [{"PK": pk} for pk in pk_values]

    # batch_get_item supports up to 100 keys per call
    all_items = []
    unprocessed = keys

    start = time.perf_counter()

    while unprocessed:
        batch = unprocessed[:100]
        unprocessed = unprocessed[100:]

        try:
            response = dynamodb.batch_get_item(
                RequestItems={
                    DYNAMODB_TABLE_NAME: {"Keys": batch}
                }
            )
        except ClientError as exc:
            raise RuntimeError(
                f"Failed to fetch items from DynamoDB: {exc}"
            ) from exc

        all_items.extend(response["Responses"].get(DYNAMODB_TABLE_NAME, []))

        # retry any unprocessed keys returned by DynamoDB
        leftover = response.get("UnprocessedKeys", {})
        if leftover.get(DYNAMODB_TABLE_NAME):
            unprocessed = leftover[DYNAMODB_TABLE_NAME]["Keys"] + unprocessed

    elapsed = time.perf_counter() - start

    return all_items, elapsed


def main():

    parser = argparse.ArgumentParser(
        description="Retrieve multiple DynamoDB records by PK and report response time."
    )

    parser.add_argument(
        "pks",
        nargs="+",
        help="One or more primary key values"
    )

    args = parser.parse_args()

    print(f"Fetching {len(args.pks)} item(s)...")

    items, elapsed = get_items_by_pks(args.pks)

    print(f"Retrieved {len(items)} item(s) in {elapsed:.3f}s")
    print()

    for item in items:
        print(json.dumps(item, indent=2, default=str))
        print()

    not_found = set(args.pks) - {item["PK"] for item in items}
    if not_found:
        print(f"Not found: {sorted(not_found)}")


if __name__ == "__main__":
    main()
