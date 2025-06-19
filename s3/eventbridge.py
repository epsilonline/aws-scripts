import typer
from botocore.exceptions import ClientError
from utils.aws import AWSHelper
from utils.s3 import get_buckets_by_tag


def set_eventbridge_notification(bucket_name: str, enable: bool):
    """
    Enables or disables EventBridge notifications for a specific bucket.

    Args:
        bucket_name: The S3 bucket name.
        enable: If True, enables EventBridge. If False, removes all notifications.
    """
    s3_client = AWSHelper.get_client("s3")

    action_text = "enabled" if enable else "disabled"
    human_action = "Enabling" if enable else "Disabling"

    if enable:
        # To enable, we add an EventBridgeConfiguration. This sends all events.
        notification_config = {'EventBridgeConfiguration': {}}
    else:
        # To disable, we set an empty NotificationConfiguration,
        # which removes ALL notification settings (SQS, SNS, Lambda, EventBridge).
        notification_config = {}

    try:
        s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_config
        )
        typer.secho(f"👍 EventBridge integration {action_text} for bucket: {bucket_name}", fg=typer.colors.GREEN)
    except ClientError as e:
        typer.secho(f"👎 Failed {human_action.lower()} EventBridge integration for {bucket_name}: {e}", fg=typer.colors.RED)


def enable_notifications(
    tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
    tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets.")
):
    """
    Enables sending all bucket events to Amazon EventBridge.
    """
    typer.echo(f"▶️  Starting process to enable EventBridge integration...")
    buckets_to_update = get_buckets_by_tag(tag_key, tag_value)

    if buckets_to_update and typer.confirm(f"Are you sure you want to ENABLE EventBridge notifications for {len(buckets_to_update)} buckets?"):
        for bucket in buckets_to_update:
            set_eventbridge_notification(bucket, enable=True)
        typer.echo("\n🎉 Process completed!")
    elif not buckets_to_update:
        typer.echo("🚫 No buckets to update. Operation finished.")
    else:
        typer.echo("🚫 Operation cancelled.")


def disable_notifications(
    tag_key: str = typer.Option(..., "--tag-key", "-k", help="The tag key to select buckets."),
    tag_value: str = typer.Option(..., "--tag-value", "-v", help="The tag value to select buckets.")
):
    """
    Disables EventBridge integration by removing ALL notification configurations from the bucket.
    """
    typer.echo(f"▶️  Starting process to disable EventBridge integration...")
    buckets_to_update = get_buckets_by_tag(tag_key, tag_value)

    if buckets_to_update:
        # The confirmation message includes a clear warning about the side effects.
        warning_message = (
            f"Are you sure you want to DISABLE EventBridge integration for {len(buckets_to_update)} buckets?\n"
            f"{typer.style('WARNING', fg=typer.colors.YELLOW, bold=True)}: This action will remove ALL notification configurations "
            f"(e.g., SQS, SNS, Lambda) from these buckets."
        )
        if typer.confirm(warning_message):
            for bucket in buckets_to_update:
                set_eventbridge_notification(bucket, enable=False)
            typer.echo("\n🎉 Process completed!")
        else:
            typer.echo("🚫 Operation cancelled.")
    elif not buckets_to_update:
        typer.echo("🚫 No buckets to update. Operation finished.")


if __name__ == "__main__":
    app = typer.Typer()

    # Add commands here
    app.command()(enable_notifications)
    app.command()(disable_notifications)
