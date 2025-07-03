import typer
from botocore.exceptions import ClientError
from utils.s3 import get_buckets_by_tag
from utils.aws import AWSHelper


def set_bucket_versioning(bucket_name: str, status: str):
    """
    Enables or disables versioning for a specific bucket.

    Args:
        bucket_name: The S3 bucket name.
        status: The versioning status ('Enabled' or 'Suspended').
    """
    s3_client = AWSHelper.get_client("s3")
    try:
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': status}
        )
        message_action = "enabled" if status == "Enabled" else "disabled (suspended)"
        typer.secho(f"👍 Versioning successfully {message_action} for bucket: {bucket_name}", fg=typer.colors.GREEN)
    except ClientError as e:
        typer.secho(f"👎 Failed to set versioning for {bucket_name}: {e}", fg=typer.colors.RED)


def enable_versioning(
    tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
    tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets.")
):
    """
    Enables versioning on S3 buckets that match a specific tag.
    """
    typer.echo(f"▶️  Starting process to enable versioning...")
    buckets_to_update = get_buckets_by_tag(tag_key, tag_value)

    if buckets_to_update and typer.confirm(f"Are you sure you want to ENABLE versioning for {len(buckets_to_update)} buckets?"):
        for bucket in buckets_to_update:
            set_bucket_versioning(bucket, "Enabled")
        typer.echo("\n🎉 Process completed!")
    elif not buckets_to_update:
        typer.echo("🚫 No buckets to update. Operation finished.")
    else:
        typer.echo("🚫 Operation cancelled.")


def disable_versioning(
    tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
    tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets.")
):
    """
    Disables (suspends) versioning on S3 buckets that match a specific tag.
    """
    typer.echo(f"▶️ Starting process to disable versioning...")
    buckets_to_update = get_buckets_by_tag(tag_key, tag_value)

    if buckets_to_update and typer.confirm(f"Are you sure you want to DISABLE (suspend) versioning for {len(buckets_to_update)} buckets?"):
        for bucket in buckets_to_update:
            set_bucket_versioning(bucket, "Suspended")
        typer.echo("\n🎉 Process completed!")
    elif not buckets_to_update:
        typer.echo("🚫 No buckets to update. Operation finished.")
    else:
        typer.echo("🚫 Operation cancelled.")


def check_buckets_versioning():
    s3_client = AWSHelper.get_client("s3")

    buckets = s3_client.list_buckets()

    versioned_buckets = []

    print("Finding buckets with enabled versioning..\n")
    for bucket in buckets['Buckets']:

        bucket_name = bucket['Name']

        try:

            if "website" not in bucket_name.lower() and "src" not in bucket_name.lower() and "source" not in bucket_name.lower():
                versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)

                if 'Status' in versioning and versioning['Status'] == 'Enabled':
                    versioned_buckets.append(bucket_name)
        except Exception as e:
            print(f"Cannot determine if versioning it's enabled for bucket '{bucket_name}': {str(e)}")

    if versioned_buckets:
        print("Buckets with enabled versioning:\n")
        for bucket in versioned_buckets:
            print(bucket)
    else:
        print("No bucket found with enabled versioning\n")


if __name__ == "__main__":
    app = typer.Typer()

    # Add commands here
    app.command()(check_buckets_versioning)
    app.command()(enable_versioning)
    app.command()(disable_versioning)
