"""
AWS S3 Batch Operations Pending Job Cleaner.

This script identifies and cancels pending S3 Batch Operations jobs
created before a specified date. It is designed to be used by DevOps engineers
to clean up stale or forgotten jobs, preventing unnecessary resource consumption
or accidental execution.

Maintained by the team at https://github.com/epsilonline/aws-scripts
"""

import logging
from datetime import datetime, timezone

import typer
from botocore.exceptions import ClientError, NoCredentialsError

from utils.aws import AWSHelper
from utils.logger import setup_logging

# --- Globals ---
APP_NAME = "s3-batch-cleaner"
logger = logging.getLogger(APP_NAME)


def clean_batch_operation_pending_jobs(
        before_date_str: str = typer.Option(
            ...,
            "--before-date",
            "-d",
            help="Date in YYYY-MM-DD format. Jobs created before this date will be cancelled.",
            prompt="Enter the cutoff date (YYYY-MM-DD)",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Simulate the script execution without actually cancelling jobs. Highly recommended for the first run.",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging.",
        ),
):
    """
    Scans for and cancels PENDING S3 Batch Operations jobs created before a specified date.

    This tool requires IAM permissions for 's3:ListJobs' and 's3:UpdateJobStatus'.
    """
    setup_logging(verbose)

    if dry_run:
        logger.info("--- DRY RUN MODE ENABLED ---")
        logger.info("No jobs will be modified. The script will only report what it would do.")

    try:
        # Parse and validate the date input. Make it timezone-aware (UTC) for correct comparison.
        cutoff_date = datetime.strptime(before_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        logger.info(f"Targeting pending jobs created before: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    except ValueError:
        logger.error(f"Invalid date format: '{before_date_str}'. Please use YYYY-MM-DD.")
        raise typer.Exit(code=1)

    try:
        s3_control_client = AWSHelper.get_client('s3control')
        sts_client = AWSHelper.get_client('sts')

        identity = sts_client.get_caller_identity()
        aws_account_id = identity['Account']

        jobs_to_cancel_count = 0
        total_jobs_scanned = 0

        # --- CORRECTED PAGINATION LOGIC ---
        # The list_jobs operation does not support an automatic paginator.
        # We must handle pagination manually using the NextToken.
        next_token = None
        while True:
            logger.debug(f"Requesting a page of jobs... (NextToken: {'Yes' if next_token else 'No'})")

            # Prepare arguments for the API call
            list_jobs_args = {
                'AccountId': aws_account_id,
                'JobStatuses': ['Suspended']
            }
            if next_token:
                list_jobs_args['NextToken'] = next_token

            response = s3_control_client.list_jobs(**list_jobs_args)
            jobs_in_page = response.get("Jobs", [])

            if not jobs_in_page and not next_token:
                logger.info("No pending jobs found in the account.")
                break

            total_jobs_scanned += len(jobs_in_page)

            for job in jobs_in_page:
                job_id = job.get('JobId')
                creation_time = job.get('CreationTime')

                logger.debug(f"Scanning job '{job_id}' created at {creation_time.isoformat()}")

                if creation_time < cutoff_date:
                    jobs_to_cancel_count += 1
                    logger.info(
                        f"MATCH: Job '{job_id}' (Created: {creation_time.strftime('%Y-%m-%d')}) is a candidate for cancellation.")

                    if not dry_run:
                        try:
                            logger.info(f"Attempting to cancel job '{job_id}'...")
                            s3_control_client.update_job_status(
                                AccountId=aws_account_id,
                                JobId=job_id,
                                RequestedJobStatus='Cancelled',
                                StatusUpdateReason='Cancelled by automated cleanup script (aws-scripts/s3_batch_cancel_pending_jobs)'
                            )
                            logger.info(f"SUCCESS: Job '{job_id}' has been cancelled.")
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code")
                            logger.error(f"FAILED to cancel job '{job_id}'. Reason: {error_code} - {e}")
                    else:
                        logger.info(f"[DRY RUN] Would have cancelled job '{job_id}'.")

            # Check if there are more pages to fetch
            next_token = response.get('NextToken')
            if not next_token:
                logger.debug("No NextToken found in response. Reached the last page.")
                break  # Exit the loop if there are no more results
        # --- END OF CORRECTED PAGINATION LOGIC ---

        logger.info("--- Scan complete ---")
        logger.info(f"Total pending jobs scanned: {total_jobs_scanned}")
        if dry_run:
            logger.info(f"Jobs that would be cancelled: {jobs_to_cancel_count}")
        else:
            logger.info(f"Jobs processed for cancellation: {jobs_to_cancel_count}")

    except NoCredentialsError:
        logger.error("AWS credentials not found. Please configure your environment (e.g., via `aws configure`).")
        raise typer.Exit(code=1)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == 'AccessDenied':
            logger.error(
                f"Access Denied. Check your IAM permissions. Required: 's3:ListJobs', 's3:UpdateJobStatus' for account {aws_account_id}.")
        else:
            logger.error(f"An AWS API error occurred: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app = typer.Typer()
    app.command()(clean_batch_operation_pending_jobs)