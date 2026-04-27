import csv
import json
import time
import pathlib
from typing import List, Tuple

import typer
from botocore.exceptions import ClientError
from utils.aws import AWSHelper

# ... (il resto della tua app Typer)

def display_summary_and_confirm(mappings: List[Tuple[str, str]]) -> None:
    """
    Displays the operation summary and asks for user confirmation.
    Aborts the execution if the user declines.
    """
    typer.secho("\n--- Operation Summary ---", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"The script will create an IAM Role and configure replication for {len(mappings)} pairs:")
    
    for src, dst in mappings:
        typer.echo(f"  - {src}  ->  {dst}")
        
    typer.echo("-" * 40)
    typer.confirm("Do you want to proceed creating IAM Roles and enabling replication?", abort=True)


def create_replication_role(iam_client, src_bucket: str, dst_bucket: str) -> str:
    """
    Creates the IAM Role and attaches a Customer Managed Policy for S3 replication,
    matching the Terraform module structure perfectly to avoid state drift.
    """
    role_name = f"{src_bucket}-replication"[:64]
    policy_name = f"{src_bucket}-replication"[:128]
    
    # 1. Trust Policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "",
                "Effect": "Allow",
                "Principal": {
                    "Service": "s3.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    typer.echo("    Creating IAM Role...")
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
        role_arn = response['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
            typer.echo(f"    Role '{role_name}' already exists.")
        else:
            raise e

    # 2. Permissions Policy (Managed Policy)
    repl_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetReplicationConfiguration",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{src_bucket}"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObjectVersion",
                    "s3:GetObjectVersionAcl",
                    "s3:GetObjectVersionForReplication"
                ],
                "Resource": [
                    f"arn:aws:s3:::{src_bucket}/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging"
                ],
                "Resource": [
                    f"arn:aws:s3:::{dst_bucket}/*"
                ]
            }
        ]
    }

    typer.echo("    Creating and Attaching IAM Managed Policy...")
    
    # Per referenziare o attaccare la policy ci serve l'Account ID corrente
    sts_client = AWSHelper.get_client('sts')
    account_id = sts_client.get_caller_identity()["Account"]
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    try:
        iam_client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(repl_policy)
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            typer.echo(f"    Policy '{policy_name}' already exists.")
        else:
            raise e

    # Associa la policy al ruolo
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_arn
    )

    typer.echo("    Waiting 10 seconds for IAM propagation...")
    time.sleep(10)
    
    return role_arn


def enable_replication(
    file_path: pathlib.Path = typer.Option(
        ..., 
        "--file", "-f", 
        help="Path to the CSV file containing source and destination buckets (format: source,destination)",
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True,
    ),
    delimiter: str = typer.Option(",", "--delimiter", help="CSV delimiter character (default is comma)")
):
    """
    Enables S3 replication reading from a CSV, automatically creating a dedicated IAM role for each bucket pair.
    """
    mappings = []
    
    # 1. Read CSV mappings
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            next(reader, None)
            for row_num, row in enumerate(reader, start=1):
                if not row: continue
                if len(row) < 2:
                    typer.secho(f"Warning: Row {row_num} skipped (invalid format): {row}", fg=typer.colors.YELLOW)
                    continue
                mappings.append((row[0].strip(), row[1].strip()))
    except Exception as e:
        typer.secho(f"Error reading CSV file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not mappings:
        typer.secho("Error: The file is empty or contains no valid bucket mappings.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 2. Display summary and wait for confirmation
    display_summary_and_confirm(mappings)

    typer.echo("\nStarting infrastructure configuration...\n")

    s3_client = AWSHelper.get_client('s3')
    iam_client = AWSHelper.get_client('iam')
    
    success_count = 0
    fail_count = 0

    # 3. Process each bucket pair
    for src, dst in mappings:
        typer.secho(f"Processing: {src} -> {dst}", fg=typer.colors.CYAN)
        
        try:
            # Create IAM Role
            role_arn = create_replication_role(iam_client, src, dst)

            # Configure S3 Replication
            typer.echo("    Configuring S3 Replication...")
            replication_config = {
                'Role': role_arn,
                'Rules': [
                    {
                        'ID': f"{src}-replication"[:255],
                        'Status': 'Enabled',
                        'Priority': 0,
                        'DeleteMarkerReplication': { 
                            'Status': 'Enabled' 
                        },
                        'Filter': { 
                            'Prefix': '' 
                        },
                        'Destination': {
                            'Bucket': f"arn:aws:s3:::{dst}",
                            'StorageClass': 'STANDARD'
                        }
                    }
                ]
            }

            s3_client.put_bucket_replication(
                Bucket=src,
                ReplicationConfiguration=replication_config
            )
            
            typer.secho("    SUCCESS: Replication enabled", fg=typer.colors.GREEN)
            success_count += 1
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            typer.secho(f"    AWS ERROR: {error_msg}", fg=typer.colors.RED, err=True)
            fail_count += 1
        except Exception as e:
            typer.secho(f"    UNEXPECTED ERROR: {str(e)}", fg=typer.colors.RED, err=True)
            fail_count += 1

    # Final Recap
    typer.echo("\n--- Final Summary ---")
    typer.secho(f"Completed: {success_count}", fg=typer.colors.GREEN)
    if fail_count > 0:
        typer.secho(f"Failed: {fail_count}", fg=typer.colors.RED)