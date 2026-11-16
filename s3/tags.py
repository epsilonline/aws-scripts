from typing import List

import typer
from botocore.exceptions import ClientError

from utils.aws import AWSHelper


def _parse_tags(raw_tags: List[str]) -> dict:
    """Converte ['K1=V1', 'K2=V2'] in {'K1': 'V1', 'K2': 'V2'}."""
    parsed = {}
    for raw in raw_tags:
        key, sep, value = raw.partition("=")
        key = key.strip()
        if not sep or not key:
            typer.secho(
                f"👎 Invalid tag '{raw}'. Expected format: KEY=VALUE",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        parsed[key] = value.strip()
    return parsed


def append_bucket_tags(
    file_path: str = typer.Option(
        ..., "--file", "-f", help="Path del file con la lista dei bucket (uno per riga)."
    ),
    tags: List[str] = typer.Option(
        ..., "--tag", "-t",
        help="Tag da aggiungere/aggiornare nel formato KEY=VALUE. Ripetibile.",
    ),
):
    """
    Fa l'append (o l'update) di uno o più tag sui bucket elencati nel file,
    preservando i tag già esistenti.
    """
    new_tags = _parse_tags(tags)
    s3_client = AWSHelper.get_client("s3")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            buckets = [line.strip() for line in f if line.strip()]
    except Exception as e:
        typer.secho(f"👎 Could not read file '{file_path}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not buckets:
        typer.echo("🚫 No buckets found in the file. Operation finished.")
        raise typer.Exit()

    tags_display = ", ".join(f"{k}={v}" for k, v in new_tags.items())
    typer.echo(f"▶️  Starting tag update for {len(buckets)} buckets...")
    typer.echo(f"   Tags to append/update: {tags_display}\n")

    if not typer.confirm(f"Are you sure you want to set [{tags_display}] on {len(buckets)} buckets?"):
        typer.echo("🚫 Operation cancelled.")
        raise typer.Exit()

    success_count = 0
    fail_count = 0

    for bucket in buckets:
        # 1. Leggo i tag esistenti
        existing_tags = []
        try:
            response = s3_client.get_bucket_tagging(Bucket=bucket)
            existing_tags = response.get("TagSet", [])
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchTagSet":
                typer.secho(f"👎 Failed reading tags for {bucket}: {e}", fg=typer.colors.RED)
                fail_count += 1
                continue

        # 2. Merge: i tag esistenti restano, quelli indicati vengono aggiunti/aggiornati
        tags_dict = {t["Key"]: t["Value"] for t in existing_tags}
        tags_dict.update(new_tags)
        final_tags = [{"Key": k, "Value": v} for k, v in tags_dict.items()]

        # 3. Scrivo
        try:
            s3_client.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": final_tags})
            typer.secho(f"👍 Tags [{tags_display}] set on bucket: {bucket}", fg=typer.colors.GREEN)
            success_count += 1
        except ClientError as e:
            typer.secho(f"👎 Failed writing tags for {bucket}: {e}", fg=typer.colors.RED)
            fail_count += 1

    typer.echo(f"\n🎉 Process completed! Success: {success_count}, Failed: {fail_count}")
    if fail_count:
        raise typer.Exit(code=1)