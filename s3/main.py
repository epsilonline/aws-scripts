import typer

from s3.inventory import add_inventory_configuration, remove_inventory_configuration
from s3.pitr import pitr, pitr_ingest_existing_objects_with_multiple_version_at_same_time
from s3.versioning import enable_versioning, disable_versioning, check_bucket_versioning
from s3.eventbridge import enable_notifications, disable_notifications

app = typer.Typer()

# Add commands here
app.command()(check_bucket_versioning)
app.command()(pitr)
app.command()(enable_versioning)
app.command()(disable_versioning)
app.command()(enable_notifications)
app.command()(disable_notifications)
app.command()(add_inventory_configuration)
app.command()(remove_inventory_configuration)
app.command()(pitr_ingest_existing_objects_with_multiple_version_at_same_time)


if __name__ == "__main__":
    app()
