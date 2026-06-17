import json
import time
import pathlib
from typing import Dict, Any, List, Optional

import typer
import yaml
from botocore.exceptions import ClientError
from utils.aws import AWSHelper

app = typer.Typer()

# --- HELPER FUNCTIONS ---

def display_summary_and_confirm(buckets_config: List[Dict[str, Any]], role_arn: Optional[str]) -> None:
    """Mostra il riepilogo delle operazioni e chiede conferma all'utente."""
    typer.secho("\n--- Operation Summary ---", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"Lo script configurerà la replica per {len(buckets_config)} bucket.")
    
    if role_arn:
        typer.echo(f"Gestione IAM: Utilizzo ruolo esistente -> {role_arn}\n")
    else:
        typer.echo("Gestione IAM: Creazione/Aggiornamento ruolo globale -> temp-replication\n")
    
    for idx, bucket_cfg in enumerate(buckets_config, start=1):
        src = bucket_cfg.get("source_bucket", "MANCANTE")
        dst = bucket_cfg.get("destination_bucket", "MANCANTE")
        cross_account = bucket_cfg.get("dest_account_id")
        account_display = f" (Cross-Account: {cross_account})" if cross_account else ""
        
        typer.echo(f"  {idx}. {src} -> {dst}{account_display}")
        
    typer.echo("-" * 40)
    typer.confirm("Vuoi procedere con la configurazione della replica?", abort=True)

def resolve_config_value(bucket_cfg: dict, config: dict, field_name: str, default_key: str, default_val=None):
    if field_name in bucket_cfg:
        return bucket_cfg[field_name]
    return config.get(default_key, default_val)

def create_global_replication_role(iam_client, role_name: str, src_buckets: List[str], dst_buckets: List[str], dry_run: bool = False) -> str:
    """
    Crea un UNICO ruolo IAM e policy globale per tutti i bucket di origine e destinazione.
    """
    policy_name = f"{role_name}-policy"[:128]
    
    if dry_run:
        typer.secho(f"    [DRY-RUN] Simulata creazione ruolo globale '{role_name}'", fg=typer.colors.YELLOW)
        typer.secho(f"    [DRY-RUN] Simulata policy globale con {len(src_buckets)} origini e {len(dst_buckets)} destinazioni", fg=typer.colors.YELLOW)
        return f"arn:aws:iam::123456789012:role/DRY-RUN-{role_name}"

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "s3.amazonaws.com"}, "Action": "sts:AssumeRole"}]
    }

    typer.echo(f"    [IAM] Verifica/Creazione ruolo globale '{role_name}'...")
    try:
        response = iam_client.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy))
        role_arn = response['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
        else:
            raise e

    src_arns = [f"arn:aws:s3:::{b}" for b in set(src_buckets)]
    src_obj_arns = [f"arn:aws:s3:::{b}/*" for b in set(src_buckets)]
    dst_obj_arns = [f"arn:aws:s3:::{b}/*" for b in set(dst_buckets)]

    repl_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetReplicationConfiguration", "s3:ListBucket"],
                "Resource": src_arns
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObjectVersion", "s3:GetObjectVersionAcl", "s3:GetObjectVersionForReplication", "s3:GetObjectVersionTagging"],
                "Resource": src_obj_arns
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ReplicateTags", "s3:GetObjectVersionTagging", "s3:ObjectOwnerOverrideToBucketOwner"],
                "Resource": dst_obj_arns
            }
        ]
    }

    sts_client = AWSHelper.get_client('sts')
    account_id = sts_client.get_caller_identity()["Account"]
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    try:
        iam_client.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(repl_policy))
        typer.echo(f"    [IAM] Policy globale '{policy_name}' creata.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            typer.echo(f"    [IAM] Aggiornamento policy globale esistente '{policy_name}'...")
            iam_client.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(repl_policy),
                SetAsDefault=True
            )
            versions = iam_client.list_policy_versions(PolicyArn=policy_arn)['Versions']
            for v in versions:
                if not v['IsDefaultVersion']:
                    iam_client.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
        else:
            raise e

    iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    typer.echo("    [IAM] Attesa 10 secondi per propagazione IAM globale...")
    time.sleep(10)
    
    return role_arn

def delete_global_replication_role(iam_client, role_name: str, dry_run: bool) -> None:
    """Elimina il ruolo globale, la sua policy associata e pulisce eventuali dipendenze residue."""
    policy_name = f"{role_name}-policy"[:128]
    
    sts_client = AWSHelper.get_client('sts')
    account_id = sts_client.get_caller_identity()["Account"]
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    if dry_run:
        typer.secho(f"    [DRY-RUN] Simulata eliminazione ruolo '{role_name}' e policy '{policy_name}'.", fg=typer.colors.YELLOW)
        return

    try:
        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        typer.echo(f"    [IAM] Policy '{policy_name}' scollegata dal ruolo.")
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            typer.secho(f"    [IAM] Avviso scollegamento policy: {e.response['Error']['Message']}", fg=typer.colors.YELLOW)

    try:
        versions = iam_client.list_policy_versions(PolicyArn=policy_arn).get('Versions', [])
        for v in versions:
            if not v['IsDefaultVersion']:
                iam_client.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
        
        iam_client.delete_policy(PolicyArn=policy_arn)
        typer.echo(f"    [IAM] Policy '{policy_name}' eliminata definitivamente.")
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            typer.secho(f"    [IAM] Avviso eliminazione policy: {e.response['Error']['Message']}", fg=typer.colors.YELLOW)

    try:
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name).get('AttachedPolicies', [])
        for pol in attached_policies:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=pol['PolicyArn'])
            typer.echo(f"    [IAM] Scollegata policy residua: {pol['PolicyName']}")
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            typer.secho(f"    [IAM] Errore controllo policy collegate: {e.response['Error']['Message']}", fg=typer.colors.RED)

    try:
        inline_policies = iam_client.list_role_policies(RoleName=role_name).get('PolicyNames', [])
        for pol_name in inline_policies:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=pol_name)
            typer.echo(f"    [IAM] Eliminata policy inline residua: {pol_name}")
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            typer.secho(f"    [IAM] Errore controllo policy inline: {e.response['Error']['Message']}", fg=typer.colors.RED)

    try:
        iam_client.delete_role(RoleName=role_name)
        typer.secho(f"    [IAM] ✓ Ruolo '{role_name}' eliminato con successo.", fg=typer.colors.GREEN)
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            typer.secho(f"    [IAM] Errore critico eliminazione ruolo: {e.response['Error']['Message']}", fg=typer.colors.RED)

def build_replication_rule(source_bucket: str, dest_bucket: str, dest_account_id: str | None, 
                           change_ownership: bool, defaults: dict, overrides: dict) -> dict:
    cfg = {**defaults, **(overrides or {})}
    
    destination = {"Bucket": f"arn:aws:s3:::{dest_bucket}"}
    if cfg.get("storage_class"): destination["StorageClass"] = cfg["storage_class"]
    if dest_account_id: destination["Account"] = str(dest_account_id)

    if change_ownership:
        if not dest_account_id:
            raise ValueError(f"Per abilitare 'change_ownership' su '{source_bucket}' serve specificare un 'dest_account_id'.")
        destination["AccessControlTranslation"] = {"Owner": "Destination"}

    return {
        "ID": f"{source_bucket}-replication"[:255],
        "Priority": cfg.get("priority", 1),
        "Filter": {"Prefix": ""},
        "Status": cfg.get("status", "Enabled"),
        "SourceSelectionCriteria": cfg.get("source_selection_criteria", {"ReplicaModifications": {"Status": "Enabled"}}),
        "Destination": destination,
        "DeleteMarkerReplication": {"Status": cfg.get("delete_marker_replication", "Enabled")}
    }

def apply_replication_rule(s3_client, source_bucket: str, role_arn: str, new_rule: dict, dry_run: bool) -> None:
    existing_rules = []
    try:
        existing = s3_client.get_bucket_replication(Bucket=source_bucket)
        existing_rules = existing.get("ReplicationConfiguration", {}).get("Rules", [])
    except ClientError as e:
        if e.response["Error"]["Code"] != "ReplicationConfigurationNotFoundError":
            raise

    filtered_rules = [r for r in existing_rules if r.get("ID") != new_rule["ID"]]
    if filtered_rules:
        max_priority = max([r.get("Priority", 0) for r in filtered_rules])
        new_rule["Priority"] = max(max_priority + 1, new_rule.get("Priority", 1))

    replication_config = {"Role": role_arn, "Rules": filtered_rules + [new_rule]}

    if dry_run:
        typer.secho("    [DRY-RUN] Nessuna modifica applicata su AWS.", fg=typer.colors.YELLOW)
        return

    s3_client.put_bucket_replication(Bucket=source_bucket, ReplicationConfiguration=replication_config)
    typer.secho("    ✓ Regola applicata con successo.", fg=typer.colors.GREEN)

def delete_replication_rule(s3_client, source_bucket: str, dest_bucket: str, dry_run: bool) -> None:
    rule_id = f"{source_bucket}-replication"[:255]
    try:
        existing = s3_client.get_bucket_replication(Bucket=source_bucket)
        existing_rules = existing.get("ReplicationConfiguration", {}).get("Rules", [])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ReplicationConfigurationNotFoundError":
            typer.secho("    [S3] Nessuna configurazione di replica trovata.", fg=typer.colors.YELLOW)
            return
        raise e
        
    filtered_rules = [r for r in existing_rules if r.get("ID") != rule_id]
    
    if len(filtered_rules) == len(existing_rules):
        typer.echo(f"    [S3] Regola '{rule_id}' non trovata.")
        return
        
    if dry_run:
        typer.secho(f"    [DRY-RUN] Simulata rimozione regola S3 '{rule_id}'.", fg=typer.colors.YELLOW)
        return
        
    if not filtered_rules:
        s3_client.delete_bucket_replication(Bucket=source_bucket)
        typer.secho("    [S3] ✓ Nessuna regola rimanente. Configurazione eliminata.", fg=typer.colors.GREEN)
    else:
        role_arn = existing["ReplicationConfiguration"]["Role"]
        replication_config = {"Role": role_arn, "Rules": filtered_rules}
        s3_client.put_bucket_replication(Bucket=source_bucket, ReplicationConfiguration=replication_config)
        typer.secho(f"    [S3] ✓ Regola '{rule_id}' rimossa con successo.", fg=typer.colors.GREEN)


# --- TYPER COMMAND ---

@app.command("enable-replication")
def enable_replication(
    config_file: pathlib.Path = typer.Option(
        ..., "--config", "-c", help="Percorso al file YAML di configurazione", exists=True
    ),
    role_arn: Optional[str] = typer.Option(
        None, "--role-arn", "-r", help="ARN completo di un ruolo IAM esistente. Se omesso, verrà creato il ruolo 'temp-replication'."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula l'operazione senza applicare modifiche"),
    cleanup_rules: bool = typer.Option(False, "--cleanup-rules", help="Rimuove le regole di replica dai bucket S3 specificati nello YAML"),
    cleanup_role: bool = typer.Option(False, "--cleanup-role", help="Rimuove il ruolo IAM globale 'temp-replication'")
):
    """Gestisce l'abilitazione o la rimozione della replica S3 tramite un file YAML e un ruolo IAM."""
    
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    if "buckets" not in config:
        typer.secho("Errore: Il file YAML deve contenere la chiave 'buckets'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    is_cleanup = cleanup_rules or cleanup_role

    if is_cleanup:
        typer.secho("\n--- CLEANUP Summary ---", fg=typer.colors.RED, bold=True)
        if cleanup_rules: typer.echo(f"  - Rimozione regole S3 per {len(config['buckets'])} configurazioni")
        if cleanup_role: typer.echo("  - Rimozione ruolo IAM: temp-replication")
        
        if not dry_run:
            typer.confirm("\nVuoi procedere con il cleanup distruttivo?", abort=True)
        else:
            typer.secho("\n--- ESECUZIONE IN MODALITÀ DRY-RUN ---", fg=typer.colors.YELLOW, bold=True)
    else:
        if not dry_run:
            display_summary_and_confirm(config["buckets"], role_arn)
        else:
            typer.secho("\n--- ESECUZIONE IN MODALITÀ DRY-RUN ---", fg=typer.colors.YELLOW, bold=True)

    s3_client = AWSHelper.get_client('s3')
    iam_client = AWSHelper.get_client('iam')
    rule_defaults = config.get("rule_defaults", {})
    success, failed = 0, 0

    active_role_arn = role_arn
    if not is_cleanup and not role_arn:
        sources = [b.get("source_bucket") for b in config["buckets"] if b.get("source_bucket")]
        destinations = [b.get("destination_bucket") for b in config["buckets"] if b.get("destination_bucket")]
        active_role_arn = create_global_replication_role(iam_client, "temp-replication", sources, destinations, dry_run=dry_run)
        typer.secho(f"\n    [!] RUOLO CREATO/AGGIORNATO CON SUCCESSO: temp-replication", fg=typer.colors.MAGENTA, bold=True)

    for bucket_cfg in config["buckets"]:
        source = bucket_cfg.get("source_bucket")
        destination = bucket_cfg.get("destination_bucket")
        
        if not source or not destination:
            continue

        if is_cleanup:
            if cleanup_rules:
                typer.secho(f"\nPulizia Regola: {source} -> {destination}", fg=typer.colors.CYAN)
                try:
                    delete_replication_rule(s3_client, source, destination, dry_run)
                    success += 1
                except Exception as e:
                    typer.secho(f"    ✗ Errore nel cleanup S3: {e}", fg=typer.colors.RED, err=True)
                    failed += 1
        else:
            typer.secho(f"\nProcessing: {source} -> {destination}", fg=typer.colors.CYAN, bold=True)
            try:
                dest_account_id = resolve_config_value(bucket_cfg, config, "dest_account_id", "default_dest_account_id")
                change_ownership = resolve_config_value(bucket_cfg, config, "change_ownership", "default_change_ownership", False)
                overrides = bucket_cfg.get("rule_overrides", {})

                rule = build_replication_rule(source, destination, dest_account_id, change_ownership, rule_defaults, overrides)
                apply_replication_rule(s3_client, source, active_role_arn, rule, dry_run)
                success += 1
            except Exception as e:
                typer.secho(f"    ✗ Errore: {e}", fg=typer.colors.RED, err=True)
                failed += 1

    # 3. CLEANUP RUOLO IAM (Eseguito una sola volta alla fine)
    if is_cleanup and cleanup_role:
        typer.secho(f"\nPulizia IAM", fg=typer.colors.CYAN, bold=True)
        if role_arn:
            typer.secho(f"    [IAM] Salto l'eliminazione perché hai fornito un ARN esplicito ({role_arn}).", fg=typer.colors.YELLOW)
        else:
            try:
                delete_global_replication_role(iam_client, "temp-replication", dry_run)
            except Exception as e:
                typer.secho(f"    ✗ Errore nel cleanup IAM: {e}", fg=typer.colors.RED, err=True)

    action_str = "Cleanup " if is_cleanup else ""
    typer.echo(f"\n--- Final {action_str}Summary ---")
    typer.secho(f"Regole elaborate con successo: {success}", fg=typer.colors.GREEN)
    if failed > 0:
        typer.secho(f"Fallimenti sulle regole: {failed}", fg=typer.colors.RED)