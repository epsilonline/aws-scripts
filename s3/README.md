# S3 Enable Replication

Questo script automatizza la configurazione della replica S3 leggendo le direttive da un file YAML. È progettato per operare in sicurezza su ambienti di produzione.

## ✨ Funzionalità Principali

* **Smart IAM:** Se specificato nel YAML, utilizza ruoli IAM esistenti; in caso contrario, crea dinamicamente i ruoli e le policy con i permessi minimi necessari.
* **Supporto Cross-Account:** Gestisce la replica tra account AWS differenti, incluso il cambio di Object Ownership (`AccessControlTranslation`).
* **Configurazione Sicura (Safe Append):** Legge le regole di replica esistenti sul bucket e aggiunge la nuova regola calcolando automaticamente la priorità, evitando di sovrascrivere configurazioni preesistenti.
* **Guardrails:** Implementa un riepilogo pre-esecuzione con conferma manuale e una modalità di simulazione completa tramite il flag `--dry-run`.

---

## 🚀 Utilizzo da CLI

Lo script si integra con Typer e va lanciato tramite il main dell'applicazione.

```bash
# Esecuzione standard
python main.py enable-replication --config path/to/config.yaml

# Esecuzione in modalità simulazione (Dry Run)
python main.py enable-replication --config path/to/config.yaml --dry-run
```

## Esempio config.yaml

```yaml

# Valori di default per Account di destinazione e Ownership
# Se la maggior parte dei bucket va verso un altro account, impostali qui.
default_dest_account_id: "999999999999" 
default_change_ownership: true

# Configurazione globale delle regole
rule_defaults:
  priority: 1
  status: "Enabled"
  storage_class: "STANDARD"
  source_selection_criteria:
    ReplicaModifications:
      Status: "Enabled"
  delete_marker_replication: "Enabled"

buckets:
  # Caso 1: Cross-account standard (usa tutti i default globali)
  - source_bucket: src-bucket-1
    destination_bucket: dest-bucket-1
    rule_overrides:
      storage_class: "STANDARD"

  # Caso 2: Stesso account (nessun cambio ownership, ignoriamo i default)
  - source_bucket: src-bucket-same-account
    destination_bucket: dest-bucket-same-account
    change_ownership: false
    dest_account_id: null # Annulla il default globale se non serve

  # Caso 3: Cross-account verso un account diverso da quello di default
  - source_bucket: src-bucket-other-account
    destination_bucket: dest-bucket-other-account
    dest_account_id: "111122223333"
    change_ownership: true
    role: arn:aws:iam::123456789012:role/s3-replication-role-specific
```