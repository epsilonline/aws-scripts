import json
import pathlib
import copy
import typer
import yaml
from botocore.exceptions import ClientError
from utils.aws import AWSHelper

app = typer.Typer()

# --- HELPER FUNCTIONS ---

def get_bucket_policy(s3_client, bucket_name: str) -> dict:
    """Recupera la policy attuale del bucket. Se non esiste, restituisce uno scheletro vuoto."""
    try:
        response = s3_client.get_bucket_policy(Bucket=bucket_name)
        policy = json.loads(response['Policy'])
        
        # Assicura che 'Statement' sia sempre una lista per facilitare le operazioni successive
        if 'Statement' in policy and isinstance(policy['Statement'], dict):
            policy['Statement'] = [policy['Statement']]
            
        return policy
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
            return {"Version": "2012-10-17", "Statement": []}
        raise e

def generate_custom_statements(bucket_name: str, template_statements: list, role_arn: str, source_account: str) -> list:
    """Copia il template e sostituisce dinamicamente i segnaposti in tutto l'oggetto."""
    if not template_statements:
        return []

    statements = copy.deepcopy(template_statements)
    
    def replace_placeholders(node):
        if isinstance(node, str):
            return node.replace("{bucket_name}", bucket_name) \
                       .replace("{replication_role_arn}", role_arn) \
                       .replace("{source_account_id}", source_account)
        elif isinstance(node, list):
            return [replace_placeholders(item) for item in node]
        elif isinstance(node, dict):
            return {key: replace_placeholders(value) for key, value in node.items()}
        return node

    for i in range(len(statements)):
        statements[i] = replace_placeholders(statements[i])
                
    return statements


# --- TYPER COMMAND ---

@app.command("manage-destination-policy")
def manage_destination_policy(
    config_file: pathlib.Path = typer.Option(
        ..., "--config", "-c", help="Percorso al file YAML di configurazione delle policy", exists=True
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula l'operazione senza applicare modifiche")
):
    """Gestisce l'aggiunta o la rimozione delle policy sui bucket di destinazione per la replica S3."""
    
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    global_enable = config.get("global_enable_replication", False)
    replication_role_arn = config.get("replication_role_arn", "")
    source_account_id = str(config.get("source_account_id", ""))
    
    # Usa 'or []' per gestire il caso in cui nello YAML la chiave sia vuota (None)
    managed_sids = config.get("managed_sids") or []
    template_statements = config.get("policy_statements_template") or []
    buckets = config.get("buckets", {})

    if not buckets:
        typer.secho("Errore: Il file YAML non contiene bucket validi.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho("\n--- Analisi Policy Bucket di Destinazione ---", fg=typer.colors.CYAN, bold=True)
    if dry_run:
        typer.secho("ESECUZIONE IN MODALITÀ DRY-RUN\n", fg=typer.colors.YELLOW, bold=True)

    s3_client = AWSHelper.get_client('s3')
    success, failed = 0, 0

    for bucket_name, settings in buckets.items():
        if settings is None:
            settings = {}
            
        enable_replication = settings.get("enable_replication", global_enable)
        status_str = "ABILITATA" if enable_replication else "DISABILITATA"
        typer.secho(f"Elaborazione bucket: {bucket_name} (Replica: {status_str})", fg=typer.colors.CYAN)

        try:
            policy = get_bucket_policy(s3_client, bucket_name)
            
            # Rimuovi SEMPRE gli statement gestiti per evitare duplicati o residui vecchi
            original_statements = policy.get("Statement", [])
            cleaned_statements = [
                stmt for stmt in original_statements 
                if stmt.get("Sid") not in managed_sids
            ]

            # Aggiungi i nuovi statement formattati se la replica è attiva
            if enable_replication:
                new_statements = generate_custom_statements(
                    bucket_name=bucket_name, 
                    template_statements=template_statements,
                    role_arn=replication_role_arn,
                    source_account=source_account_id
                )
                cleaned_statements.extend(new_statements)
                typer.echo("    [+] Statement generati pronti per l'inserimento.")
            else:
                typer.echo("    [-] Statement rimossi o ignorati.")

            policy["Statement"] = cleaned_statements

            # Applica o elimina la policy
            if not policy["Statement"]:
                if dry_run:
                    typer.secho(f"    [DRY-RUN] Simulata ELIMINAZIONE totale policy (nessuno statement rimasto).", fg=typer.colors.YELLOW)
                else:
                    s3_client.delete_bucket_policy(Bucket=bucket_name)
                    typer.secho("    [*] Nessuno statement rimasto. Policy eliminata.", fg=typer.colors.GREEN)
            else:
                if dry_run:
                    typer.secho(f"    [DRY-RUN] Simulata SCRITTURA policy aggiornata.", fg=typer.colors.YELLOW)
                else:
                    s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                    typer.secho("    [*] Policy aggiornata con successo.", fg=typer.colors.GREEN)
            
            success += 1
        except Exception as e:
            typer.secho(f"    [!] Errore gestione policy: {e}", fg=typer.colors.RED, err=True)
            failed += 1

    typer.echo("\n--- Riepilogo Gestione Policy ---")
    typer.secho(f"Elaborati con successo: {success}", fg=typer.colors.GREEN)
    if failed > 0:
        typer.secho(f"Falliti: {failed}", fg=typer.colors.RED)

if __name__ == "__main__":
    app()