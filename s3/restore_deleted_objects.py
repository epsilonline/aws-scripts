import typer
from botocore.exceptions import ClientError
from s3.versioning import check_bucket_versioning
from utils.aws import AWSHelper
from utils.logger import get_logger

logger = get_logger(__name__)


def restore_all_deleted_objects(bucket_name: str):
    s3_client = AWSHelper.get_client("s3")
    """
    Scans an S3 bucket, finds all objects with a delete marker,
    and restores them by deleting the marker itself.
    """
    # Step 1: Verify versioning is active. It's the core requirement.
    if not check_bucket_versioning(s3_client, bucket_name):
        raise typer.Exit(code=1)

    logger.info(f"Starting restoration process for bucket: '{bucket_name}'")
    restored_count = 0
    markers_found = 0

    try:
        # Paginator is the right way to handle large buckets efficiently.
        paginator = s3_client.get_paginator('list_object_versions')
        pages = paginator.paginate(Bucket=bucket_name, MaxKeys=200) # Smaller page size for better feedback

        for page in pages:
            # The 'DeleteMarkers' field may not exist on a page if there are none.
            if 'DeleteMarkers' in page:
                delete_markers = page['DeleteMarkers']
                markers_found += len(delete_markers)

                for marker in delete_markers:
                    key = marker['Key']
                    version_id = marker['VersionId']

                    logger.info(f"Found delete marker for object '{key}' (VersionId: {version_id})")
                    logger.info(f"  -> Restoring object by removing its delete marker...")

                    # To "restore" the object, we simply delete the "delete marker" version.
                    s3_client.delete_object(
                        Bucket=bucket_name,
                        Key=key,
                        VersionId=version_id
                    )

                    logger.info(f"  -> Successfully restored object '{key}'.")
                    restored_count += 1

    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            logger.error("ACCESS DENIED. Check your IAM permissions.")
            logger.error("Required permissions: 's3:ListBucketVersions' and 's3:DeleteObjectVersion'.")
        else:
            logger.error(f"An unexpected AWS error occurred: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"A generic error occurred: {e}")
        raise typer.Exit(code=1)

    # --- Final Summary ---
    logger.info("--- Process Completed ---")
    if markers_found == 0:
        logger.info("✅ No deleted objects (delete markers) were found in the bucket.")
    else:
        logger.info(f"Found a total of {markers_found} delete markers.")
        logger.info(f"✅ Successfully restored {restored_count} objects.")


if __name__ == "__main__":
    app = typer.Typer(help="""
    A CLI tool to restore all deleted objects in a versioned S3 bucket.

    It works by finding all delete markers and removing them,
    which effectively restores the previous version of the object.
    """)

    app.command()(restore_all_deleted_objects)