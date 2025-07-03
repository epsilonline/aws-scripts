import typer

from s3.inventory import add_inventory_configuration, remove_inventory_configuration
from s3.pitr import pitr, pitr_ingest_existing_objects_with_multiple_versions_at_same_time
from s3.restore_deleted_objects import restore_all_deleted_objects
from s3.versioning import enable_versioning, disable_versioning, check_buckets_versioning
from s3.eventbridge import enable_notifications, disable_notifications
from s3.s3_batch_operations import clean_batch_operation_pending_jobs
app = typer.Typer()

# Add commands here
app.command()(check_buckets_versioning)
app.command()(pitr)
app.command()(enable_versioning)
app.command()(disable_versioning)
app.command()(enable_notifications)
app.command()(disable_notifications)
app.command()(add_inventory_configuration)
app.command()(remove_inventory_configuration)
app.command()(pitr_ingest_existing_objects_with_multiple_versions_at_same_time)
app.command()(clean_batch_operation_pending_jobs)
app.command()(restore_all_deleted_objects)

if __name__ == "__main__":
    app()
