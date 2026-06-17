import pathlib
import typer
from botocore.exceptions import ClientError
from utils.aws import AWSHelper

app = typer.Typer()

# --- HELPER FUNCTIONS ---

def get_object_metadata(s3_client, bucket: str, key: str) -> dict:
    """Return object size and storage class."""
    response = s3_client.head_object(Bucket=bucket, Key=key)
    return {
        "size": response["ContentLength"],
        "storage_class": response.get("StorageClass", "STANDARD")
    }

def simple_copy(s3_client, source_bucket: str, dest_bucket: str, key: str, storage_class: str) -> bool:
    """Single-part copy for objects <= 5GB."""
    try:
        s3_client.copy_object(
            CopySource={"Bucket": source_bucket, "Key": key},
            Bucket=dest_bucket,
            Key=key,
            StorageClass=storage_class,
        )
        typer.secho(f"  ✅ Simple copy OK: {key} (StorageClass: {storage_class})", fg=typer.colors.GREEN)
        return True
    except ClientError as e:
        typer.secho(f"  ❌ Simple copy failed: {key} — {e}", fg=typer.colors.RED, err=True)
        return False

def multipart_copy(s3_client, source_bucket: str, dest_bucket: str, key: str, size: int, storage_class: str, part_size: int, max_retries: int) -> bool:
    """Multipart copy for objects > 5GB."""
    mpu = None
    try:
        mpu = s3_client.create_multipart_upload(
            Bucket=dest_bucket,
            Key=key,
            StorageClass=storage_class,
        )
        upload_id = mpu["UploadId"]
        typer.echo(f"  Multipart upload started — UploadId: {upload_id}")

        parts = []
        part_number = 1
        offset = 0

        while offset < size:
            end = min(offset + part_size - 1, size - 1)
            copy_range = f"bytes={offset}-{end}"

            typer.echo(f"  Uploading part {part_number} — range {copy_range}")

            for attempt in range(1, max_retries + 1):
                try:
                    response = s3_client.upload_part_copy(
                        Bucket=dest_bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        CopySource={"Bucket": source_bucket, "Key": key},
                        CopySourceRange=copy_range,
                    )
                    parts.append({
                        "PartNumber": part_number,
                        "ETag": response["CopyPartResult"]["ETag"]
                    })
                    break
                except ClientError as e:
                    typer.secho(f"  Part {part_number} attempt {attempt} failed: {e}", fg=typer.colors.YELLOW)
                    if attempt == max_retries:
                        raise

            part_number += 1
            offset = end + 1

        s3_client.complete_multipart_upload(
            Bucket=dest_bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )
        typer.secho(f"  ✅ Multipart copy OK: {key} ({len(parts)} parts, StorageClass: {storage_class})", fg=typer.colors.GREEN)
        return True

    except ClientError as e:
        typer.secho(f"  ❌ Multipart copy failed: {key} — {e}", fg=typer.colors.RED, err=True)
        if mpu:
            try:
                s3_client.abort_multipart_upload(
                    Bucket=dest_bucket,
                    Key=key,
                    UploadId=mpu["UploadId"]
                )
                typer.echo(f"  Multipart upload aborted for: {key}")
            except ClientError as abort_err:
                typer.secho(f"  Failed to abort multipart upload: {abort_err}", fg=typer.colors.RED, err=True)
        return False

def copy_object(s3_client, source_bucket: str, dest_bucket: str, key: str, part_size: int, max_retries: int) -> bool:
    """Auto-select simple or multipart copy based on object size."""
    try:
        meta = get_object_metadata(s3_client, source_bucket, key)
        size = meta["size"]
        storage_class = meta["storage_class"]
        size_gb = size / (1024 ** 3)
        typer.secho(f"Processing: {key} ({size_gb:.2f} GB, StorageClass: {storage_class})", fg=typer.colors.CYAN)

        if size <= 5 * 1024 ** 3:  # <= 5GB
            return simple_copy(s3_client, source_bucket, dest_bucket, key, storage_class)
        else:
            return multipart_copy(s3_client, source_bucket, dest_bucket, key, size, storage_class, part_size, max_retries)

    except ClientError as e:
        typer.secho(f"  ❌ Cannot get object size: {key} — {e}", fg=typer.colors.RED, err=True)
        return False


# --- TYPER COMMAND ---

@app.command("multipart-copy")
def multipart_copy(
    source_bucket: str = typer.Option(..., "--source", "-s", help="Nome del bucket di origine"),
    dest_bucket: str = typer.Option(..., "--dest", "-d", help="Nome del bucket di destinazione"),
    keys_file: pathlib.Path = typer.Option(
        ..., "--file", "-f", 
        help="Percorso al file di testo contenente le chiavi degli oggetti (una per riga)", 
        exists=True, dir_okay=False, readable=True
    ),
    part_size_mb: int = typer.Option(500, help="Dimensione delle parti in MB (min 5, max 5000)"),
    max_retries: int = typer.Option(3, help="Tentativi massimi per il caricamento di ogni singola parte")
):
    """
    Copia oggetti da un bucket all'altro. Usa automaticamente la copia Multipart per i file superiori a 5GB.
    """
    
    # 1. Lettura delle chiavi dal file
    with open(keys_file, "r") as f:
        # Pulisce le righe da spazi vuoti e salta le righe vuote
        failed_objects = [line.strip() for line in f if line.strip()]
        
    total = len(failed_objects)
    if total == 0:
        typer.secho("Il file fornito è vuoto.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    s3_client = AWSHelper.get_client('s3')
    part_size_bytes = part_size_mb * 1024 * 1024

    typer.echo("─" * 60)
    typer.echo(f"Starting copy of {total} objects")
    typer.echo(f"Source : s3://{source_bucket}")
    typer.echo(f"Dest   : s3://{dest_bucket}")
    typer.echo("─" * 60)

    success = 0
    failed = []

    # 2. Ciclo di copia
    for i, key in enumerate(failed_objects, 1):
        typer.secho(f"\n[{i}/{total}]", bold=True)
        if copy_object(s3_client, source_bucket, dest_bucket, key, part_size_bytes, max_retries):
            success += 1
        else:
            failed.append(key)

    # 3. Riepilogo e salvataggio dei fallimenti
    typer.echo("\n" + "─" * 60)
    typer.secho(f"✅ Success : {success}/{total}", fg=typer.colors.GREEN)
    
    if failed:
        typer.secho(f"❌ Failed  : {len(failed)}/{total}", fg=typer.colors.RED)
        retry_file = "failed_retry.txt"
        with open(retry_file, "w") as f:
            for key in failed:
                f.write(f"{key}\n")
        typer.secho(f"Gli oggetti falliti sono stati salvati in '{retry_file}' per futuri tentativi.", fg=typer.colors.YELLOW)
    else:
        typer.secho("Tutti gli oggetti sono stati copiati con successo!", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()