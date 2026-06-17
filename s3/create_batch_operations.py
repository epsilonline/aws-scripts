import uuid
import time
import pathlib
import json

import typer
import yaml
from botocore.exceptions import ClientError
from utils.aws import AWSHelper

app = typer.Typer()

def wait_and_start_job(s3control_client, account_id: str, job_id: str) -> None:
    """Fa polling dello stato del job e invia la conferma appena passa in 'Suspended'."""
    typer.echo(f"   ⏳ In attesa che il job {job_id} finisca la fase di 'Preparing' (calcolo oggetti)...")
    
    while True:
        try:
            response = s3control_client.describe_job(AccountId=account_id, JobId=job_id)
            status = response['Job']['Status']
            
            if status == 'Suspended':
                typer.secho(f"   🚀 Il job è pronto! Invio della conferma di avvio...", fg=typer.colors.CYAN)
                s3control_client.update_job_status(
                    AccountId=account_id,
                    JobId=job_id,
                    RequestedJobStatus='Ready',
                    StatusUpdateReason='Auto-started via Python Typer CLI'
                )
                typer.secho(f"   ✅ Job confermato e ufficialmente in esecuzione!\n", fg=typer.colors.GREEN, bold=True)
                break
            elif status in ['Failed', 'Cancelled', 'Complete']:
                typer.secho(f"   ❌ Impossibile avviare il job. Lo stato è passato a: {status}\n", fg=typer.colors.RED, err=True)
                break
                
            time.sleep(5)
        except ClientError as e:
            typer.secho(f"   ❌ Errore durante il polling del job: {e}", fg=typer.colors.RED, err=True)
            break


def create_s3_batch_job(s3control_client, global_settings: dict, job: dict, dry_run: bool) -> str:
    """Crea la Batch Operation usando il ManifestGenerator automatico."""
    client_request_token = str(uuid.uuid4())
    account_id = str(global_settings['account_id'])
    
    if dry_run:
        typer.secho(f"    [DRY-RUN] Simulata creazione Job da {job['source_bucket']} a {job['dest_bucket']}", fg=typer.colors.YELLOW)
        return "job-id-simulato-12345"

    try:
        response = s3control_client.create_job(
            AccountId=account_id,
            ConfirmationRequired=True,
            Description=job['source_bucket'].split(':')[-1][:256],
            Priority=10,
            RoleArn=global_settings['role_arn'],
            ClientRequestToken=client_request_token,
            Operation={
                'S3PutObjectCopy': {
                    'TargetResource': job['dest_bucket'],
                    'MetadataDirective': 'COPY',
                    'StorageClass': 'STANDARD',
                    'RequesterPays': False,
                    'BucketKeyEnabled': False,
                    'AccessControlGrants': [
                        {
                            'Grantee': {
                                'TypeIdentifier': 'id',
                                'Identifier': global_settings['dest_canonical_id']
                            },
                            'Permission': 'FULL_CONTROL'
                        }
                    ]
                }
            },
            ManifestGenerator={
                'S3JobManifestGenerator': {
                    'SourceBucket': job['source_bucket'],
                    'Filter': {},
                    'EnableManifestOutput': False
                }
            },
            Report={
                'Bucket': global_settings['report_bucket_arn'],
                'Format': 'Report_CSV_20180820',
                'Enabled': True,
                'Prefix': job['report_prefix'],
                'ReportScope': 'FailedTasksOnly'
            }
        )
        
        job_id = response['JobId']
        typer.secho(f"✅ Job creato: {job['source_bucket']} -> {job['dest_bucket']}", fg=typer.colors.GREEN)
        typer.echo(f"   Job ID: {job_id}")
        
        # Auto-start o attesa manuale
        if global_settings.get('auto_start', False):
            wait_and_start_job(s3control_client, account_id, job_id)
        else:
            typer.secho(f"   ⏸️ Auto-start disattivato. In attesa di conferma manuale sulla console AWS.\n", fg=typer.colors.YELLOW)
            
        return job_id

    except ClientError as e:
        typer.secho(f"❌ Errore API AWS durante la creazione per {job['source_bucket']}: {e}\n", fg=typer.colors.RED, err=True)
    except Exception as e:
        typer.secho(f"❌ Errore inaspettato: {str(e)}\n", fg=typer.colors.RED, err=True)
        
    return None


@app.command("create-batch-operations")
def create_batch_operations(
    config_file: pathlib.Path = typer.Option(
        ..., "--config", "-c", help="Percorso al file YAML di configurazione", exists=True
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula l'operazione senza creare i job su AWS")
):
    """Crea (e opzionalmente avvia) AWS S3 Batch Operations basate su YAML."""
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
        
    if "global_settings" not in config or "jobs" not in config:
        typer.secho("Errore: Il file YAML deve contenere 'global_settings' e 'jobs'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
        
    settings = config['global_settings']
    jobs = config['jobs']
    
    # Inizializza il client s3control
    try:
        s3control_client = AWSHelper.get_client('s3control', region_name=settings.get('region', 'eu-west-1'))
    except TypeError:
        import boto3
        s3control_client = boto3.client('s3control', region_name=settings.get('region', 'eu-west-1'))

    typer.echo("-" * 60)
    typer.secho(f"Inizio elaborazione di {len(jobs)} job da {config_file.name}", fg=typer.colors.CYAN, bold=True)
    if dry_run:
        typer.secho("MODALITÀ DRY-RUN ATTIVA", fg=typer.colors.YELLOW, bold=True)
    typer.echo("-" * 60 + "\n")
    
    success = 0
    for job in jobs:
        if create_s3_batch_job(s3control_client, settings, job, dry_run):
            success += 1
            
    typer.echo("-" * 60)
    typer.secho(f"Elaborazione completata. Job avviati/creati: {success}/{len(jobs)}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()