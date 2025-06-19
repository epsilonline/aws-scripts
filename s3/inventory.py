import typer
from botocore.exceptions import ClientError
import json
import logging
from utils.s3 import get_buckets_by_tag
from utils.aws import AWSHelper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def add_bucket_policy_for_inventory(destination_bucket: str, source_account_id: str):
    """
    Adds the required policy to the destination bucket to allow S3 to write inventory reports.
    """
    s3 = AWSHelper.get_client('s3')
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3InventoryPolicy",
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::{destination_bucket}/*",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": source_account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": "arn:aws:s3:::*"
                    }
                }
            }
        ]
    }
    try:
        s3.put_bucket_policy(Bucket=destination_bucket, Policy=json.dumps(policy))
        logging.info(f"Policy successfully applied to destination bucket '{destination_bucket}'.")
    except ClientError as e:
        logging.error(f"Failed to apply policy to bucket '{destination_bucket}': {e}")
        raise typer.Exit(code=1)


def add_inventory_configuration(
        inventory_destination_bucket: str = typer.Option(..., "--destination-bucket", "-d",
                                               help="The S3 bucket where inventory reports will be saved."),
        prefix: str = typer.Option("inventory", "--prefix", "-p",
                                   help="The prefix for inventory reports in the destination bucket."),
        include_all_versions: bool = typer.Option(
            True,
            "--all-versions/--current-version",
            help="Choose whether to include all object versions or only current ones."
        ),
        tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
        tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets."),
        inventory_id: str = typer.Option("aws-script", "-i", help="The id of inventory configuration.")
):
    """
    Enables S3 Inventory on all buckets in the account, saving reports
    to the specified destination bucket.
    """
    s3 = AWSHelper.get_client('s3')
    sts = AWSHelper.get_client('sts')
    logging.info(f"▶️ Starting process to enable inventory configuration...")

    try:
        account_id = sts.get_caller_identity()["Account"]
    except ClientError as e:
        logging.error(f"Failed to get Account ID: {e}")
        raise typer.Exit(code=1)

    logging.info(f"Detected Account ID: {account_id}")
    logging.info(f"Configuring destination bucket: '{inventory_destination_bucket}'")
    versions_to_include = "All" if include_all_versions else "Current"
    logging.info(f"Object version mode: '{versions_to_include}'")

    source_buckets = get_buckets_by_tag(tag_key=tag_key, tag_value=tag_value)

    if source_buckets and typer.confirm(f"Are you sure you want to add inventory configuration with id '{inventory_id}' for {len(source_buckets)} buckets?"):
        add_bucket_policy_for_inventory(inventory_destination_bucket, account_id)

        for bucket_name in source_buckets:
            if bucket_name == inventory_destination_bucket:
                logging.warning(f"Skipping destination bucket '{bucket_name}'.")
                continue

            logging.info(f"Enabling inventory for bucket: '{bucket_name}'...")

            inventory_configuration = {
                "Destination": {
                    "S3BucketDestination": {"AccountId": account_id, "Bucket": f"arn:aws:s3:::{inventory_destination_bucket}",
                                            "Format": "CSV", "Prefix": f"{prefix}/{bucket_name}"}},
                "IsEnabled": True,
                "Id": inventory_id,
                "IncludedObjectVersions": versions_to_include,
                "OptionalFields": ["LastModifiedDate"],
                "Schedule": {"Frequency": "Weekly"}
            }

            try:
                s3.put_bucket_inventory_configuration(Bucket=bucket_name, Id=inventory_id,
                                                      InventoryConfiguration=inventory_configuration)
                typer.secho(f"👍 Inventory successfully enabled for bucket: {bucket_name}",
                            fg=typer.colors.GREEN)

                logging.info(f"Inventory successfully enabled for '{bucket_name}'.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidRequest' and 'already exists' in str(e):
                    typer.secho(f"An inventory configuration with ID '{inventory_id}' already exists for bucket '{bucket_name}'. Skipping.", fg=typer.colors.YELLOW)
                else:
                    typer.secho(f"👎 Error enabling inventory for '{bucket_name}': {e}", fg=typer.colors.RED)
    elif not source_buckets:
        typer.echo("🚫 No buckets to update. Operation finished.")
    else:
        typer.echo("🚫 Operation cancelled.")

        typer.secho("\nEnable operation completed! 🚀", fg=typer.colors.GREEN)


def remove_inventory_configuration(
        tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
        tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets."),
        inventory_id: str = typer.Option("aws-script", "-i", help="The id of inventory configuration.")
    ):
    """
    Removes the S3 Inventory configuration from all buckets in the account,
    assuming the configuration ID follows the 'inventory-config-{bucket_name}' format.
    """
    s3 = AWSHelper.get_client('s3')

    bucket_names = get_buckets_by_tag(tag_key=tag_key, tag_value=tag_value)
    logging.info(f"Found {len(bucket_names)} buckets to check for inventory removal.")

    source_buckets = get_buckets_by_tag(tag_key=tag_key, tag_value=tag_value)

    if source_buckets and typer.confirm(f"Are you sure you want to remove inventory configuration with id '{inventory_id}' for {len(source_buckets)} buckets?"):

        for bucket_name in source_buckets:

            logging.info(f"Attempting to remove configuration '{inventory_id}' from bucket '{bucket_name}'...")

            try:
                s3.delete_bucket_inventory_configuration(
                    Bucket=bucket_name,
                    Id=inventory_id
                )
                logging.info(f"Inventory configuration '{inventory_id}' successfully removed from '{bucket_name}'.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchConfiguration':
                    logging.warning(
                        f"No configuration with ID '{inventory_id}' found for bucket '{bucket_name}'. Skipping.")
                else:
                    logging.error(f"Error during inventory removal from bucket '{bucket_name}': {e}")
    elif not source_buckets:
        typer.echo("🚫 No buckets to update. Operation finished.")
    else:
        typer.echo("🚫 Operation cancelled.")
    typer.secho("\nRemove operation completed! ✨", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app = typer.Typer()

    # Add commands here
    app.command()(remove_inventory_configuration)
    app.command()(add_inventory_configuration)
