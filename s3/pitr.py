import boto3
import csv
import os
import time
import typer
from botocore.exceptions import ClientError
import logging
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote
from typing import Dict, Any, List
from utils.aws import AWSHelper
from pathlib import Path

file_path = Path(__file__)
script_folder_path = file_path.parent

logger = logging.getLogger('PITR')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

s3control_client = boto3.client('s3control')
athena_client = boto3.client('athena')
s3_client = boto3.client('s3')
glue_client = boto3.client("glue")

# AWS Configuration (placeholders - will be overridden by Typer arguments)
ATHENA_DATABASE = 'pitr-demo-wtzb6eiepe-s3-db'
S3_OUTPUT_LOCATION = 's3://pitr-demo-wtzb6eiepe-destination/results/'
BACKUP_S3_BUCKET = 's3://pitr-demo-wtzb6eiepe-destination/'
BACKUP_S3_PREFIX = 'pitr/'
BUCKET_COLUMN_NAME = 'bucketname'
SEQUENCER_COLUMN_NAME = 'sequencer'
TABLE_NAME = 'events-pitr_demo_wtzb6eiepe_7ihznpek1f_inventory'
QUERIES_FOLDER = script_folder_path / 'queries/'

time_validation_regex = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")

ACTION_CONFIGURATION = {
    "restore": {
        "athena_query_name": "get_files_to_restore.sql",
        "s3_batch_action": "copy"
    },
    "delete": {
        "athena_query_name": "get_files_to_delete.sql",
        "s3_batch_action": "delete"
    }
}


def get_sequencer_value(v: dict):
    return int(v.get(SEQUENCER_COLUMN_NAME, "0") or "0", 16)


def raise_error(msg: str, exit: bool = True):
    logger.error(msg)
    if exit:
        raise typer.Exit(code=1)


def start_crawler_glue(crawler_name: str, polling_interval: int = 10, timeout: int = 900) -> bool:
    """
    Start AWS Glue Crowler and wait completition.

    Args:
        crawler_name (str): Nome del crawler da avviare.
        polling_interval (int): Intervallo in secondi tra i controlli dello stato.
        timeout (int): Tempo massimo di attesa in secondi (default: 15 minuti).
    Returns:
        bool: True se l'avvio è riuscito, False altrimenti.
    """

    try:
        response = glue_client.start_crawler(Name=crawler_name)
        logger.info(f"Crawler '{crawler_name}' started.")
        elapsed = 0
        while elapsed < timeout:
            response = glue_client.get_crawler(Name=crawler_name)
            state = response['Crawler']['State']

            if state == "READY":
                logger.info(f"Crawler '{crawler_name}' completed.")
                return True
            else:
                logger.info(f"Actual state: {state}. Wait for {polling_interval} seconds...")
                time.sleep(polling_interval)
                elapsed += polling_interval

        logger.info(f"Timeout reached after {timeout} seconds. Crowler not completed.")
        return False

    except ClientError as e:
        if e.response['Error']['Code'] == 'CrawlerRunningException':
            logger.info(f"Crawler '{crawler_name}' already in execution.")
        else:
            logger.info(f"Error while starting crawler {e}")
        return False


def run_athena_query(database: str, query: str, output_location: str):
    """Runs an Athena query and returns the query execution ID."""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': database
        },
        ResultConfiguration={
            'OutputLocation': output_location
        }
    )
    return response['QueryExecutionId']


def wait_for_query_completion(query_execution_id: str):
    """Waits for an Athena query to complete."""
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = response['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            return state
        time.sleep(5)


def download_s3_file(bucket: str, key: str, local_path: str):
    """Downloads a file from S3."""
    s3_client.download_file(bucket, key, local_path)


def split_csv_file(file_path: str, split_column_name: str, extra_name_suffix: str = ""):
    """Splits a CSV file based on a specified column."""
    split_files = {}
    with open(file_path, 'r') as infile:
        reader = csv.DictReader(infile)
        if split_column_name not in reader.fieldnames:
            raise ValueError(f"Split column '{split_column_name}' not found in CSV headers.")

        for row in reader:
            split_value = row[split_column_name]
            if split_value not in split_files:
                # Create a new file for this split value
                split_files[split_value] = open(f'{"_".join([split_value, extra_name_suffix])}.csv', 'w', newline='')
            writer = csv.DictWriter(split_files[split_value], fieldnames=reader.fieldnames)
            writer.writerow(row)

    # Close all split files
    for f in split_files.values():
        f.close()

    return [f'{"_".join([value, extra_name_suffix])}.csv' for value in split_files.keys()]


def parse_athena_csv_for_restore(file_path: str, extra_name_suffix: str = "",
                                 skip_duplicated_version_at_same_time: bool = False):
    """
        Splits a CSV file based on column that contain bucket name and for each object key ensure that exist only row
        that contain last recent version based on sequencer value if exist.
        This value is hex value and highest mean more recent version.
        If exist 2 rows with same key and different version without sequencer value, mean that have error in import
        existing objects job.
        # For more information refer:
        https://aws.amazon.com/it/blogs/storage/manage-event-ordering-and-duplicate-events-with-amazon-s3-event-notifications/
    """
    split_files = {}
    duplicated_version_at_same_time_rows = {}
    row_to_write_by_bucket_name_key = {}
    with open(file_path, 'r') as infile:
        reader = csv.DictReader(infile)
        if BUCKET_COLUMN_NAME not in reader.fieldnames:
            raise ValueError(f"Split column '{BUCKET_COLUMN_NAME}' not found in CSV headers.")

        for row in reader:
            bucket_name = row[BUCKET_COLUMN_NAME]
            row_key = row["key"]
            row_sequencer = get_sequencer_value(row)
            if bucket_name not in row_to_write_by_bucket_name_key:
                # Create a new file for this split value
                row_to_write_by_bucket_name_key[bucket_name] = {}
            rows_to_write = row_to_write_by_bucket_name_key[bucket_name]
            if row_key in rows_to_write:
                last_written_row_with_same_key = rows_to_write[row_key]
                last_written_row_with_same_key_sequencer = get_sequencer_value(last_written_row_with_same_key)
                if row_sequencer < last_written_row_with_same_key_sequencer:
                    logger.info(f"Skip row for '{bucket_name}/{row_key}' because was found row with most highest "
                                f"sequencer value")
                    logger.debug(f"row_sequencer < last_written_row_by_key_sequencer: "
                                 f"{row_sequencer} < {last_written_row_with_same_key_sequencer}")
                    # Skip this row
                    continue
                elif row_sequencer == last_written_row_with_same_key_sequencer:
                    if row["version"] == last_written_row_with_same_key["version"]:
                        logging.debug("Found duplicated row")
                    elif row_sequencer == 0:
                        if skip_duplicated_version_at_same_time:
                            duplicated_version_at_same_time_rows[row_key] = row
                    elif row["version"] != last_written_row_with_same_key["version"]:
                        if skip_duplicated_version_at_same_time:
                            duplicated_version_at_same_time_rows[row_key] = row
                            logging.info(f"Skip object {bucket_name}/{row_key}")
                            continue
                        else:
                            raise Exception("Multiple version with at same event time ingested detect")
            # If execution reach this line, mean that we need write this row
            row_to_write_by_bucket_name_key[bucket_name][row_key] = row

        for bucket_name in row_to_write_by_bucket_name_key.keys():
            f = split_files[bucket_name] = open(f'{"_".join([bucket_name, extra_name_suffix])}.csv', 'w', newline='')
            writer = csv.DictWriter(f, fieldnames=['bucketname', 'key', 'version'])
            rows = [{
                        'bucketname': v['bucketname'],
                        'key': v['key'],
                        'version': v['version']
                     } for _, v in row_to_write_by_bucket_name_key[bucket_name].items()]
            writer.writerows(rows)
            f.close()

        with open('duplicated_version_at_same_time.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["bucketname", "key", "version", "sequencer"])
            writer.writerows([v for _, v in duplicated_version_at_same_time_rows.items()])

    return [f'{"_".join([value, extra_name_suffix])}.csv' for value in split_files.keys()]


def upload_to_s3(bucket: str, prefix: str, file_paths: list):
    """Uploads files to S3."""
    for file_path in file_paths:
        s3_key = f'{prefix}{os.path.basename(file_path)}'
        s3_client.upload_file(file_path, bucket, s3_key)
        logger.info(f"Uploaded {file_path} to s3://{bucket}/{s3_key}")


def start_s3_batch_operation(manifest_s3_uri: str, destination_bucket: str, iam_role_arn: str, action: str,
                             report_bucket_arn: str,
                             batch_delete_lambda_function_arn: str = None, confirmation_required: bool = False):
    """Starts an S3 Batch Operations job using a Lambda function."""
    destination_bucket_arn = f"arn:aws:s3:::{destination_bucket}"
    operation = {}
    manifest_fields = []
    if action == "copy":
        operation = {
            'S3PutObjectCopy': {
                'TargetResource': destination_bucket_arn,
                'MetadataDirective': 'COPY',
                'StorageClass': 'INTELLIGENT_TIERING'
            }
        }
        manifest_fields = ['Bucket', 'Key', 'VersionId']
    elif action == "delete":
        if not batch_delete_lambda_function_arn:
            raise_error("For delete action batch-lambda-delete-function-arn it's required")
        operation = {
            'LambdaInvoke': {
                'FunctionArn': batch_delete_lambda_function_arn,
                'InvocationSchemaVersion': '1.0'
            }
        }
        manifest_fields = ['Bucket', 'Key']

    else:
        raise_error("Invalid action")

    manifest_bucket_key = manifest_s3_uri.replace('s3://', '').split('/')
    manifest_s3 = s3_client.head_object(Bucket=manifest_bucket_key[0], Key='/'.join(manifest_bucket_key[1:]))
    if not manifest_s3:
        raise_error("Invalid manifest file")

    response = s3control_client.create_job(
        AccountId=boto3.client('sts').get_caller_identity()['Account'],  # Get current account ID
        ConfirmationRequired=confirmation_required,
        Operation=operation,
        Report={
            'Bucket': destination_bucket_arn,  # Report bucket is usually the same or a different designated bucket
            'Format': 'Report_CSV_20180820',
            'Enabled': True,
            "ReportScope": "AllTasks",
            'Prefix': 'batch-operations-report',
        },
        Manifest={
            'Spec': {
                'Format': 'S3BatchOperations_CSV_20180820',
                'Fields': manifest_fields
            },
            'Location': {
                'ObjectArn': f'arn:aws:s3:::{manifest_s3_uri.split("s3://")[1]}',
                "ETag": manifest_s3['ETag'],
                **({"ObjectVersionId": manifest_s3.get('VersionId')} if 'VersionId' in manifest_s3 else {})
            }
        },
        Priority=10,
        RoleArn=iam_role_arn,
        Description=f'Restore with PITR bucket {destination_bucket}'
    )
    return response['JobId']


def do_action(
        athena_database: str = typer.Option(..., help="The Athena database to query."),
        athena_table: str = typer.Option(..., help="The Athena table to query."),
        action: str = typer.Option(..., help="The action to perform"),
        s3_temp_bucket: str = typer.Option(..., help="The S3 bucket for storing query results and split file backups."),
        start_time: str = typer.Option(..., help="Start time to restore window"),
        end_time: str = typer.Option(..., help="End time to restore window"),
        restore_iam_role_arn: str = typer.Option(..., help="IAM role used for batch operations"),
        batch_lambda_delete_arn: str = typer.Option(..., help="ARN of lambda for delete in batch mperation"),
        confirmation_required: bool = typer.Option(False, help="If True don't start batch operation"),
        skip_duplicated_version_at_same_time: bool = typer.Option(False, help="If true skip restore of object "
                                                                              "with duplicated version at same time")
):
    """
    Runs an Athena query from a file, exports results to CSV, splits the CSV by a column,
    and uploads the split files to an S3 temp location, start glue jons.
    """
    # Read query from file
    query_path = f"{QUERIES_FOLDER}/{ACTION_CONFIGURATION[action]['athena_query_name']}"
    s3_query_result_prefix = f"results/"
    s3_query_result_uri = f"s3://{s3_temp_bucket}/{s3_query_result_prefix}"
    s3_bucket_manifest_prefix = f"manifests/"
    s3_bucket_batch_operation_manifest_uri = f"s3://{s3_temp_bucket}/{s3_bucket_manifest_prefix}"

    try:
        with open(query_path, 'r') as f:
            athena_query = f.read()
    except FileNotFoundError:
        logger.error(f"Error: Query file not found at {query_path}")
        raise typer.Exit(code=1)

    # Substitute variables in query
    athena_query = athena_query.replace("$TABLE_NAME", athena_table)
    athena_query = athena_query.replace("$START_TIME", start_time)
    athena_query = athena_query.replace("$END_TIME", end_time)

    # 1. Run Athena Query
    logger.info("Running Athena query...")
    query_execution_id = run_athena_query(athena_database, athena_query, s3_query_result_uri)
    logger.info(f"Query Execution ID: {query_execution_id}")

    # 2. Wait for query completion
    logger.info("Waiting for query completion...")
    state = wait_for_query_completion(query_execution_id)
    logger.info(f"Query state: {state}")

    if state == 'SUCCEEDED':
        # Determine the output file key
        # Athena adds .csv and .metadata files with the query execution ID as the name
        output_key = f"{s3_query_result_uri.split('s3://')[1]}{query_execution_id}.csv"
        local_csv_file = 'athena_results.csv'

        # Download the result file
        logger.info(f"Downloading results from s3://{s3_query_result_uri.split('s3://')[1]}{query_execution_id}.csv...")
        key_name = '/'.join(s3_query_result_uri.split('s3://')[1].split('/')[1:]) + f"{query_execution_id}.csv"

        try:
            download_s3_file(s3_temp_bucket, key_name, local_csv_file)
            logger.info(f"Downloaded to {local_csv_file}")
        except Exception as e:
            logger.error(f"Error downloading file from S3: {e}")
            return

        # 3. Split the CSV file
        try:
            if action == 'restore':
                logger.info(f"Splitting CSV file by column '{BUCKET_COLUMN_NAME} and remove duplicated key'...")
                split_files = parse_athena_csv_for_restore(local_csv_file, extra_name_suffix=action,
                                                           skip_duplicated_version_at_same_time=
                                                           skip_duplicated_version_at_same_time)
            else:
                logger.info(f"Splitting CSV file by column '{BUCKET_COLUMN_NAME}'...")
                split_files = split_csv_file(local_csv_file, BUCKET_COLUMN_NAME, extra_name_suffix=action)
            logger.info(f"Split into files: {split_files}")

            # 4. Upload split files to S3
            logger.info(f"Uploading split files to {s3_bucket_batch_operation_manifest_uri}...")
            upload_to_s3(s3_temp_bucket, s3_bucket_manifest_prefix, split_files)
            logger.info("Prepare batch manifests operation complete.")

            # Clean up local files
            # os.remove(local_csv_file)
            # for split_file in split_files:
            #     os.remove(split_file)
            for bucket_to_restore in split_files:
                logger.info(f"Start batch operation for restore old version in bucket: {bucket_to_restore}")
                manifest_s3_uri = f"{s3_bucket_batch_operation_manifest_uri}{bucket_to_restore}"
                batch_operation_action = ACTION_CONFIGURATION[action]["s3_batch_action"]
                # name contains action split for get bucket name
                bucket_to_restore = bucket_to_restore.split('_')[0]
                start_s3_batch_operation(manifest_s3_uri, bucket_to_restore, restore_iam_role_arn,
                                         action=batch_operation_action,
                                         batch_delete_lambda_function_arn=batch_lambda_delete_arn,
                                         confirmation_required=confirmation_required)

        except ValueError as e:
            logger.error(f"Error splitting CSV: {e}")
        except Exception as e:
            logger.error(f"An error occurred during splitting or uploading: {e}")

    else:
        logger.error("Athena query did not succeed.")


# ToDo use tags for get values
def pitr(
        athena_database: str = typer.Option(..., help="The Athena database to query."),
        athena_table: str = typer.Option(..., help="The Athena table to query."),

        delete_file: bool = typer.Option(False, help="Start glue jobs for delete objects"),
        s3_temp_bucket: str = typer.Option(..., help="The S3 bucket for storing query results and split file backups."),

        start_time: str = typer.Option(..., help="Start time to restore window. Allowed format: 2025-05-30T04:00:00Z "),
        end_time: str = typer.Option(..., help="End time to restore window. Allowed format: 2025-05-30T04:00:00Z"),

        restore_iam_role_arn: str = typer.Option(..., help="IAM role used for batch operations"),
        batch_lambda_delete_arn: str = typer.Option(..., help="ARN of lambda for delete in batch operation"),

        crawler_name: str = typer.Option(None, help="Glue crawler name, if not provided skip start crawler before "
                                                    "run queries."),
        crawler_polling_interval: int = typer.Option(10, help="Crawler status polling interval"),
        crawler_timeout: int = typer.Option(900, help="Timeout in seconds before mark as filed crawler execution"),
        dry_run: bool = typer.Option(False, help="Timeout in seconds before mark as filed crawler execution"),
        skip_duplicated_version_at_same_time: bool = typer.Option(False, help="If true skip restore of object "
                                                                              "with duplicated version at same time")
):
    if not time_validation_regex.match(start_time) or not time_validation_regex.match(end_time):
        raise_error("Invalid start_time or end_time, use allowed format: 2025-05-30T04:00:00Z ", exit=True)

    if crawler_name:
        start_crawler_glue(crawler_name,
                           polling_interval=crawler_polling_interval,
                           timeout=crawler_timeout)
    do_action(
        athena_database=athena_database,
        athena_table=athena_table,
        action="restore",
        s3_temp_bucket=s3_temp_bucket,
        start_time=start_time,
        end_time=end_time,
        restore_iam_role_arn=restore_iam_role_arn,
        batch_lambda_delete_arn=batch_lambda_delete_arn,
        confirmation_required=dry_run,
        skip_duplicated_version_at_same_time=skip_duplicated_version_at_same_time
    )
    if delete_file:
        do_action(
            athena_database=athena_database,
            athena_table=athena_table,
            action="delete",
            s3_temp_bucket=s3_temp_bucket,
            start_time=start_time,
            end_time=end_time,
            restore_iam_role_arn=restore_iam_role_arn,
            batch_lambda_delete_arn=batch_lambda_delete_arn,
            confirmation_required=dry_run
        )


def get_latest_s3_version(s3_client: boto3.client, bucket_name: str, key: str) -> Dict[str, Any] | None:
    """
    Fetches the latest version information for a given S3 object.
    Returns a dictionary with processed data or None if no latest version is found or an error occurs.
    """
    try:
        response = s3_client.list_object_versions(Bucket=bucket_name, Prefix=key)
        versions = response.get("Versions", [])
        delete_markers = response.get("DeleteMarkers", [])

        all_versions = sorted(
            versions + delete_markers,
            key=lambda x: x['LastModified'],
            reverse=True
        )

        latest_version = None
        for ver in all_versions:
            if ver.get('IsLatest'):
                latest_version = ver
                break

        if not latest_version and all_versions:  # Fallback
            latest_version = all_versions[0]

        if latest_version:
            event_time_iso = latest_version['LastModified'].isoformat(timespec='seconds').replace('+00:00', 'Z')
            return {
                "eventTime": event_time_iso,
                "bucketName": bucket_name,
                "key": key,
                "version": latest_version.get("VersionId", "null"),
                "eventName": "Object Created",
                "sourceIPAddress": "10.202.9.225"
            }
        else:
            logger.warning(f"No versions found for {bucket_name}/{key}. Skipping.")
            return None

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            logger.error(f"Bucket '{bucket_name}' not found. Skipping {bucket_name}/{key}.")
        else:
            logger.error(f"AWS error processing {bucket_name}/{key}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred for {bucket_name}/{key}: {e}")
        return None


def pitr_ingest_existing_objects_with_multiple_versions_at_same_time(
        input_csv: str = typer.Argument(..., help="Path to the input CSV file."),
        output_json: str = typer.Option(None, help="Path to the output JSON file."),
        max_workers: int = typer.Option(10, help="Maximum number of parallel workers for S3 API calls."),

):
    """
     Reads a CSV, finds the latest S3 object version for each unique bucketName/key pair,
     and outputs the results to a JSON file.
     """
    s3_client = AWSHelper.get_client('s3')
    processed_data: List[Dict[str, Any]] = []

    if not output_json:
        output_json = f"{''.join(input_csv.split('.')[0])}-pitr-events"

    logger.info(f"Starting to process CSV file: {input_csv}")

    unique_objects: Dict[str, Dict[str, str]] = {}
    try:
        with open(input_csv, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                bucket_name = row.get("bucketName")
                key = unquote(row.get("key"))

                if not bucket_name or not key:
                    logger.warning(f"Skipping row due to missing bucketName or key: {row}")
                    continue

                unique_key = f"{bucket_name}/{key}"
                if unique_key not in unique_objects:
                    unique_objects[unique_key] = {"bucketName": bucket_name, "key": key}

        logger.info(f"Identified {len(unique_objects)} unique bucketName/key pairs.")

    except FileNotFoundError:
        logger.error(f"Error: Input CSV file not found at {input_csv}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"An error occurred while reading CSV: {e}")
        raise typer.Exit(code=1)

    # Use ThreadPoolExecutor for parallel S3 calls
    # boto3 clients are thread-safe for calls, but each thread needs its own client
    # or you can share one if it's not being modified. For simple gets, sharing is fine.
    # However, it's generally safer and clearer to create a new client for each worker in a thread pool.
    # boto3 docs suggest creating a client per thread for most use cases,
    # or using Session to explicitly manage thread-safety.
    # For this pattern, recreating client in the worker function is often preferred.

    # We will pass the bucket_name and key to the worker function.
    # The worker function itself will create a boto3 client if needed,
    # or we can create one per thread with a callable initializer for the pool.
    # For simplicity and robust threading, let's pass the client to the worker.
    # Note: boto3 clients are thread-safe for *concurrent* calls, but not for *modification*.
    # Here, we are only making calls, so a single client instance passed to multiple threads is generally fine.
    # If you encounter issues with a shared client in a high-concurrency scenario, consider
    # instantiating `boto3.client("s3")` inside `get_latest_s3_version`.

    logger.info(f"Starting parallel S3 version lookups with {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_latest_s3_version, s3_client, obj["bucketName"], obj["key"]):
                f"{obj['bucketName']}/{obj['key']}"
            for obj in unique_objects.values()
        }

        for i, future in enumerate(as_completed(futures), 1):
            obj_path = futures[future]
            try:
                result = future.result()
                if result:
                    processed_data.append(result)
            except Exception as exc:
                logger.error(f'{obj_path} generated an exception: {exc}')

            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(unique_objects)} objects...")

    logger.info(f"Finished processing S3 versions. Writing {len(processed_data)} entries to {output_json}")

    try:
        with open(output_json, 'w', encoding='utf-8') as outfile:
            for entry in processed_data:
                outfile.write(json.dumps(entry) + '\n')

        logger.info("Processing complete.")
    except Exception as e:
        logger.error(f"An error occurred while writing output JSON: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(pitr)
    # print(parse_athena_csv_for_restore("athena_results.csv", extra_name_suffix="sequencer_test"))
    # start_s3_batch_operation("s3://pitr-demo-wtzb6eiepe-7ihznpek1f-temp/manifests/usbim-browser-dev-bucket-15218383_restore.csv",
    #                          destination_bucket="usbim-browser-dev-bucket-15218383",
    #                          iam_role_arn="pitr-demo-wtzb6eiepe-restore-role", action="copy")
