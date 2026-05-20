import argparse
import boto3
from botocore.exceptions import ClientError


DYNAMODB_TABLE_NAME = "oead_student_features"
AWS_REGION = "us-east-1"


def get_item_by_pk(pk_value):
    """Fetch a single DynamoDB item by its partition key (PK)."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    try:
        response = table.get_item(Key={"PK": pk_value})
    except ClientError as exc:
        raise RuntimeError(f"Failed to fetch item from DynamoDB: {exc}") from exc

    return response.get("Item")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve a DynamoDB record by PK from the oead_student_features table."
    )
    parser.add_argument("pk", help="Primary key value to lookup")
    args = parser.parse_args()

    item = get_item_by_pk(args.pk)
    if item is None:
        print(f"No item found for PK={args.pk}")
        return

    import json

    print(json.dumps(item, indent=2, default=str))


if __name__ == "__main__":
    main()
