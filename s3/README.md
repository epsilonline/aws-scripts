# S3 Management Tools

A comprehensive collection of command-line tools for managing AWS S3 buckets, including versioning, replication, inventory, point-in-time recovery (PITR), event notifications, batch operations, and intelligent object copying.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Available Commands](#available-commands)
  - [Versioning Management](#versioning-management)
  - [EventBridge Notifications](#eventbridge-notifications)
  - [S3 Inventory](#s3-inventory)
  - [Point-in-Time Recovery (PITR)](#point-in-time-recovery-pitr)
  - [Deleted Objects Recovery](#deleted-objects-recovery)
  - [S3 Replication](#s3-replication)
  - [Batch Operations](#batch-operations)
  - [Object Copy Operations](#object-copy-operations)
- [Configuration Files](#configuration-files)
- [Common Workflows](#common-workflows)

## Prerequisites

- Python 3.8+
- AWS credentials configured (`aws configure`)
- Required IAM permissions for S3, IAM, EventBridge, Glue, and Athena operations
- Poetry (for dependency management)

## Installation

```bash
# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

## Available Commands

All commands are executed through the main entry point:

```bash
python -m s3.main [COMMAND] [OPTIONS]
```

---

## Versioning Management

### `check-buckets-versioning`

Lists all S3 buckets in your account that have versioning enabled.

**Usage:**
```bash
python -m s3.main check-buckets-versioning
```

**Example:**
```bash
python -m s3.main check-buckets-versioning
# Output:
# Finding buckets with enabled versioning..
# 
# Buckets with enabled versioning:
# 
# my-production-bucket
# my-backup-bucket
# data-archive-bucket
```

---

### `enable-versioning`

Enables versioning on S3 buckets that match specific tags.

**Usage:**
```bash
python -m s3.main enable-versioning --tag-key <KEY> --tag-value <VALUE>
```

**Parameters:**
- `--tag-key, -k` (required): Tag key to filter buckets
- `--tag-value, -v` (required): Tag value to filter buckets

**Example:**
```bash
# Enable versioning on all buckets tagged with Environment=production
python -m s3.main enable-versioning \
  --tag-key Environment \
  --tag-value production

# Expected output:
# ▶️  Starting process to enable versioning...
# Are you sure you want to ENABLE versioning for 5 buckets? [y/N]: y
# 👍 Versioning successfully enabled for bucket: prod-data-bucket
# 👍 Versioning successfully enabled for bucket: prod-backup-bucket
# ...
# 🎉 Process completed!
```

---

### `disable-versioning`

Disables (suspends) versioning on S3 buckets that match specific tags.

**Usage:**
```bash
python -m s3.main disable-versioning --tag-key <KEY> --tag-value <VALUE>
```

**Parameters:**
- `--tag-key, -k` (required): Tag key to filter buckets
- `--tag-value, -v` (required): Tag value to filter buckets

**Example:**
```bash
# Disable versioning on test buckets
python -m s3.main disable-versioning \
  --tag-key Environment \
  --tag-value test

# Expected output:
# ▶️ Starting process to disable versioning...
# Are you sure you want to DISABLE (suspend) versioning for 3 buckets? [y/N]: y
# 👍 Versioning successfully disabled (suspended) for bucket: test-bucket-1
# 🎉 Process completed!
```

**Note:** Disabling versioning does not delete existing versions; it only suspends version creation for new uploads.

---

## EventBridge Notifications

### `enable-notifications`

Enables EventBridge integration to send all S3 bucket events to Amazon EventBridge.

**Usage:**
```bash
python -m s3.main enable-notifications --tag-key <KEY> --tag-value <VALUE>
```

**Parameters:**
- `--tag-key, -k` (required): Tag key to filter buckets
- `--tag-value, -v` (required): Tag value to filter buckets

**Example:**
```bash
# Enable EventBridge notifications for monitoring buckets
python -m s3.main enable-notifications \
  --tag-key Monitor \
  --tag-value true

# Expected output:
# ▶️  Starting process to enable EventBridge integration...
# Are you sure you want to ENABLE EventBridge notifications for 4 buckets? [y/N]: y
# 👍 EventBridge integration enabled for bucket: analytics-bucket
# 👍 EventBridge integration enabled for bucket: logs-bucket
# 🎉 Process completed!
```

---

### `disable-notifications`

Disables EventBridge integration by removing ALL notification configurations from buckets.

**Usage:**
```bash
python -m s3.main disable-notifications --tag-key <KEY> --tag-value <VALUE>
```

**Parameters:**
- `--tag-key, -k` (required): Tag key to filter buckets
- `--tag-value, -v` (required): Tag value to filter buckets

**Example:**
```bash
python -m s3.main disable-notifications \
  --tag-key Monitor \
  --tag-value false
```

**⚠️ WARNING:** This command removes ALL notification configurations (SQS, SNS, Lambda, EventBridge) from the selected buckets.

---

## S3 Inventory

### `add-inventory-configuration`

Enables S3 Inventory on buckets selected by tags, saving inventory reports to a specified destination bucket.

**Usage:**
```bash
python -m s3.main add-inventory-configuration \
  --destination-bucket <DEST_BUCKET> \
  --tag-key <KEY> \
  --tag-value <VALUE> \
  [OPTIONS]
```

**Parameters:**
- `--destination-bucket, -d` (required): S3 bucket where inventory reports will be saved
- `--tag-key, -k` (required): Tag key to filter source buckets
- `--tag-value, -v` (required): Tag value to filter source buckets
- `--prefix, -p` (optional): Prefix for inventory reports (default: "inventory")
- `--all-versions/--current-version` (optional): Include all versions or current only (default: all versions)
- `-i` (optional): Inventory configuration ID (default: "aws-script")

**Example:**
```bash
# Add inventory configuration to production buckets
python -m s3.main add-inventory-configuration \
  --destination-bucket my-inventory-bucket \
  --tag-key Environment \
  --tag-value production \
  --prefix inventory-prod \
  --all-versions \
  -i prod-inventory

# Expected output:
# ▶️ Starting process to enable inventory configuration...
# Detected Account ID: 123456789012
# Configuring destination bucket: 'my-inventory-bucket'
# Object version mode: 'All'
# Are you sure you want to add inventory configuration with id 'prod-inventory' for 10 buckets? [y/N]: y
# Policy successfully applied to destination bucket 'my-inventory-bucket'.
# 👍 Inventory successfully enabled for bucket: prod-bucket-1
# 👍 Inventory successfully enabled for bucket: prod-bucket-2
# ...
```

---

### `remove-inventory-configuration`

Removes S3 Inventory configurations from buckets selected by tags.

**Usage:**
```bash
python -m s3.main remove-inventory-configuration \
  --tag-key <KEY> \
  --tag-value <VALUE> \
  [OPTIONS]
```

**Parameters:**
- `--tag-key, -k` (required): Tag key to filter buckets
- `--tag-value, -v` (required): Tag value to filter buckets
- `-i` (optional): Inventory configuration ID to remove (default: "aws-script")

**Example:**
```bash
# Remove inventory configuration from test buckets
python -m s3.main remove-inventory-configuration \
  --tag-key Environment \
  --tag-value test \
  -i test-inventory
```

---

## Point-in-Time Recovery (PITR)

### `pitr`

Orchestrates Point-In-Time Recovery for S3 buckets, including starting Glue crawlers, running Athena queries, and initiating S3 Batch Operations to restore/delete objects to a specific point in time.

**Usage:**
```bash
python -m s3.main pitr \
  --athena-database <DATABASE> \
  --athena-table <TABLE> \
  --s3-temp-bucket <BUCKET> \
  --snapshot-end-time <TIMESTAMP> \
  --restore-iam-role-arn <ROLE_ARN> \
  --batch-lambda-delete-arn <LAMBDA_ARN> \
  [OPTIONS]
```

**Parameters:**
- `--athena-database` (required): Athena database name
- `--athena-table` (required): Athena table name containing S3 event data
- `--s3-temp-bucket` (required): S3 bucket for query results and manifest files
- `--snapshot-end-time` (required): Restore point timestamp (format: `YYYY-MM-DDTHH:MM:SSZ`)
- `--restore-iam-role-arn` (required): IAM role ARN for batch operations
- `--batch-lambda-delete-arn` (required): Lambda function ARN for delete operations
- `--crawler-name` (optional): Glue crawler name to run before queries
- `--crawler-polling-interval` (optional): Crawler status polling interval in seconds (default: 10)
- `--crawler-timeout` (optional): Crawler timeout in seconds (default: 900)
- `--dry-run` (optional): Simulate without creating batch operations
- `--skip-delete-objects` (optional): Skip deletion of objects created after snapshot time
- `--skip-duplicated-versions-at-same-time` (optional): Skip objects with duplicate versions at same time
- `--buckets-to-skip` (optional): Comma-separated list of buckets to skip
- `--buckets-to-restore` (optional): Comma-separated list of buckets to restore (if empty, restores all)

**Example:**
```bash
# Restore buckets to a specific point in time
python -m s3.main pitr \
  --athena-database pitr_database \
  --athena-table s3_events_table \
  --s3-temp-bucket pitr-temp-bucket \
  --snapshot-end-time "2026-01-15T12:00:00Z" \
  --restore-iam-role-arn "arn:aws:iam::123456789012:role/S3BatchOperationsRole" \
  --batch-lambda-delete-arn "arn:aws:lambda:eu-west-1:123456789012:function:S3DeleteFunction" \
  --crawler-name pitr-crawler \
  --dry-run

# Expected output:
# Crawler 'pitr-crawler' started.
# Actual state: RUNNING. Wait for 10 seconds...
# Crawler 'pitr-crawler' completed.
# Running Athena query...
# Query Execution ID: abc123-def456-...
# Waiting for query completion...
# Query state: SUCCEEDED
# Downloading results from s3://...
# Splitting CSV file by column 'bucketname' and remove duplicated key'...
# Start batch operation for restore old version in bucket: prod-bucket
# [DRY-RUN] Nessuna modifica applicata su AWS.
```

---

### `pitr-ingest-existing-objects-with-multiple-versions-at-same-time`

Processes a CSV file to identify the latest S3 object versions for objects with multiple versions created at the same time, outputting results to JSON format for PITR ingestion.

**Usage:**
```bash
python -m s3.main pitr-ingest-existing-objects-with-multiple-versions-at-same-time \
  <INPUT_CSV> \
  [OPTIONS]
```

**Parameters:**
- `INPUT_CSV` (required): Path to input CSV file
- `--output-json` (optional): Path to output JSON file
- `--max-workers` (optional): Maximum parallel workers for S3 API calls (default: 10)

**Example:**
```bash
# Process duplicated versions CSV
python -m s3.main pitr-ingest-existing-objects-with-multiple-versions-at-same-time \
  duplicated_version_at_same_time.csv \
  --output-json pitr-events.json \
  --max-workers 20

# Expected output:
# Starting to process CSV file: duplicated_version_at_same_time.csv
# Identified 150 unique bucketName/key pairs.
# Starting parallel S3 version lookups with 20 workers...
# Processed 100/150 objects...
# Finished processing S3 versions. Writing 150 entries to pitr-events.json
# Processing complete.
```

---

## Deleted Objects Recovery

### `restore-all-deleted-objects`

Scans an S3 bucket for objects with delete markers and restores them by removing the markers, effectively recovering deleted objects.

**Usage:**
```bash
python -m s3.main restore-all-deleted-objects <BUCKET_NAME>
```

**Parameters:**
- `BUCKET_NAME` (required): Name of the S3 bucket

**Example:**
```bash
# Restore all deleted objects in a bucket
python -m s3.main restore-all-deleted-objects my-backup-bucket

# Expected output:
# Checking versioning status for bucket 'my-backup-bucket'...
# Confirmed: Versioning is 'Enabled' for bucket 'my-backup-bucket'.
# Starting restoration process for bucket: 'my-backup-bucket'
# Found delete marker for object 'documents/report.pdf' (VersionId: xyz123)
#   -> Restoring object by removing its delete marker...
#   -> Successfully restored object 'documents/report.pdf'.
# Found delete marker for object 'images/logo.png' (VersionId: abc456)
#   -> Restoring object by removing its delete marker...
#   -> Successfully restored object 'images/logo.png'.
# --- Process Completed ---
# Found a total of 2 delete markers.
# ✅ Successfully restored 2 objects.
```

**Prerequisites:**
- Bucket must have versioning enabled
- Required IAM permissions: `s3:ListBucketVersions`, `s3:DeleteObjectVersion`

---

## S3 Replication

### `enable-replication`

Configures S3 replication rules based on a YAML configuration file, supporting same-region and cross-region replication, cross-account replication, IAM role management, and cleanup operations.

**Usage:**
```bash
python -m s3.main enable-replication \
  --config <CONFIG_FILE> \
  [OPTIONS]
```

**Parameters:**
- `--config, -c` (required): Path to YAML configuration file
- `--role-arn, -r` (optional): ARN of existing IAM role (if omitted, creates `temp-replication` role)
- `--dry-run` (optional): Simulate without applying changes
- `--cleanup-rules` (optional): Remove replication rules from specified buckets
- `--cleanup-role` (optional): Remove the `temp-replication` IAM role

**Example:**
```bash
# Enable replication using config file
python -m s3.main enable-replication \
  --config replication_config.yaml

# Expected output:
# --- Operation Summary ---
# Lo script configurerà la replica per 3 bucket.
# Gestione IAM: Creazione/Aggiornamento ruolo globale -> temp-replication
# 
#   1. source-bucket-1 -> dest-bucket-1
#   2. source-bucket-2 -> dest-bucket-2 (Cross-Account: 987654321098)
#   3. source-bucket-3 -> dest-bucket-3
# Vuoi procedere con la configurazione della replica? [y/N]: y
# 
#     [IAM] Verifica/Creazione ruolo globale 'temp-replication'...
#     [IAM] Policy globale 'temp-replication-policy' creata.
#     [IAM] Attesa 10 secondi per propagazione IAM globale...
# 
# Processing: source-bucket-1 -> dest-bucket-1
#     ✓ Regola applicata con successo.
# ...
# --- Final Summary ---
# Regole elaborate con successo: 3
```

**Cleanup Example:**
```bash
# Remove replication rules and IAM role
python -m s3.main enable-replication \
  --config replication_config.yaml \
  --cleanup-rules \
  --cleanup-role

# Dry-run before cleanup
python -m s3.main enable-replication \
  --config replication_config.yaml \
  --cleanup-rules \
  --cleanup-role \
  --dry-run
```

**Configuration File Example** (`replication_config.yaml`):
```yaml
# Global defaults
default_dest_account_id: "987654321098"
default_change_ownership: true

rule_defaults:
  priority: 1
  status: "Enabled"
  storage_class: "INTELLIGENT_TIERING"
  delete_marker_replication: "Enabled"
  source_selection_criteria:
    ReplicaModifications:
      Status: "Enabled"

buckets:
  - source_bucket: "my-source-bucket-1"
    destination_bucket: "my-dest-bucket-1"
    dest_account_id: "987654321098"
    change_ownership: true
    
  - source_bucket: "my-source-bucket-2"
    destination_bucket: "my-dest-bucket-2"
    rule_overrides:
      storage_class: "STANDARD"
      priority: 2
```

---

### `manage-destination-policy`

Manages bucket policies for S3 replication destination buckets, adding or removing required policy statements based on configuration.

**Usage:**
```bash
python -m s3.main manage-destination-policy \
  --config <CONFIG_FILE> \
  [OPTIONS]
```

**Parameters:**
- `--config, -c` (required): Path to YAML policy configuration file
- `--dry-run` (optional): Simulate without applying changes

**Example:**
```bash
# Manage destination bucket policies
python -m s3.main manage-destination-policy \
  --config replica_bucket_policy_config.yaml

# Expected output:
# --- Analisi Policy Bucket di Destinazione ---
# Elaborazione bucket: dest-bucket-1 (Replica: ABILITATA)
#     [+] Statement generati pronti per l'inserimento.
#     [*] Policy aggiornata con successo.
# Elaborazione bucket: dest-bucket-2 (Replica: DISABILITATA)
#     [-] Statement rimossi o ignorati.
#     [*] Nessuno statement rimasto. Policy eliminata.
# --- Riepilogo Gestione Policy ---
# Elaborati con successo: 2
```

**Configuration File Example:**
```yaml
global_enable_replication: true
replication_role_arn: "arn:aws:iam::123456789012:role/temp-replication"
source_account_id: "123456789012"

managed_sids:
  - "ReplicationPermissions"
  - "ReplicationOwnerOverride"

policy_statements_template:
  - Sid: "ReplicationPermissions"
    Effect: "Allow"
    Principal:
      AWS: "{replication_role_arn}"
    Action:
      - "s3:ReplicateObject"
      - "s3:ReplicateDelete"
    Resource: "arn:aws:s3:::{bucket_name}/*"
    
  - Sid: "ReplicationOwnerOverride"
    Effect: "Allow"
    Principal:
      AWS: "{replication_role_arn}"
    Action: "s3:ObjectOwnerOverrideToBucketOwner"
    Resource: "arn:aws:s3:::{bucket_name}/*"

buckets:
  dest-bucket-1:
    enable_replication: true
  dest-bucket-2:
    enable_replication: false
```

---

## Batch Operations

### `create-batch-operations`

Creates AWS S3 Batch Operations jobs based on a YAML configuration file, supporting manifest generation and automatic job start.

**Usage:**
```bash
python -m s3.main create-batch-operations \
  --config <CONFIG_FILE> \
  [OPTIONS]
```

**Parameters:**
- `--config, -c` (required): Path to YAML configuration file
- `--dry-run` (optional): Simulate without creating jobs on AWS

**Example:**
```bash
# Create batch operations from config
python -m s3.main create-batch-operations \
  --config batch_operations_config.yaml

# Expected output:
# ------------------------------------------------------------
# Inizio elaborazione di 3 job da batch_operations_config.yaml
# ------------------------------------------------------------
# 
# ✅ Job creato: arn:aws:s3:::source-bucket-1 -> arn:aws:s3:::dest-bucket-1
#    Job ID: 12345678-abcd-1234-efgh-1234567890ab
#    ⏳ In attesa che il job finisca la fase di 'Preparing'...
#    🚀 Il job è pronto! Invio della conferma di avvio...
#    ✅ Job confermato e ufficialmente in esecuzione!
# 
# ✅ Job creato: arn:aws:s3:::source-bucket-2 -> arn:aws:s3:::dest-bucket-2
#    Job ID: 23456789-bcde-2345-fghi-234567890abc
# ...
# ------------------------------------------------------------
# Elaborazione completata. Job avviati/creati: 3/3
```

**Configuration File Example** (`batch_operations_config.yaml`):
```yaml
global_settings:
  account_id: "123456789012"
  role_arn: "arn:aws:iam::123456789012:role/S3BatchOperationsRole"
  report_bucket_arn: "arn:aws:s3:::batch-operations-reports"
  dest_canonical_id: "abcd1234efgh5678..."
  region: "eu-west-1"
  auto_start: true

jobs:
  - source_bucket: "arn:aws:s3:::source-bucket-1"
    dest_bucket: "arn:aws:s3:::dest-bucket-1"
    report_prefix: "reports/job1"
    
  - source_bucket: "arn:aws:s3:::source-bucket-2"
    dest_bucket: "arn:aws:s3:::dest-bucket-2"
    report_prefix: "reports/job2"
```

---

### `clean-batch-operation-pending-jobs`

Scans for and cancels pending S3 Batch Operations jobs created before a specified date. Useful for cleaning up stale or forgotten jobs.

**Usage:**
```bash
python -m s3.main clean-batch-operation-pending-jobs \
  --before-date <DATE> \
  [OPTIONS]
```

**Parameters:**
- `--before-date, -d` (required): Cutoff date in YYYY-MM-DD format
- `--dry-run` (optional): Simulate without cancelling jobs
- `--verbose, -v` (optional): Enable DEBUG logging

**Example:**
```bash
# Clean up pending jobs created before 2026-01-01
python -m s3.main clean-batch-operation-pending-jobs \
  --before-date 2026-01-01 \
  --dry-run \
  --verbose

# Expected output:
# --- DRY RUN MODE ENABLED ---
# No jobs will be modified. The script will only report what it would do.
# Targeting pending jobs created before: 2026-01-01 00:00:00 UTC
# Requesting a page of jobs... (NextToken: No)
# Scanning job 'job-id-123' created at 2025-12-15T10:30:00+00:00
# MATCH: Job 'job-id-123' (Created: 2025-12-15) is a candidate for cancellation.
# [DRY RUN] Would have cancelled job 'job-id-123'.
# --- Scan complete ---
# Total pending jobs scanned: 10
# Jobs that would be cancelled: 3

# Actually cancel jobs (remove --dry-run)
python -m s3.main clean-batch-operation-pending-jobs \
  --before-date 2026-01-01
```

---

## Object Copy Operations

### `multipart-copy`

Copies objects from a source bucket to a destination bucket, automatically selecting simple or multipart copy based on object size (>5GB). Logs failed objects for retry.

**Usage:**
```bash
python -m s3.main multipart-copy \
  --source <SOURCE_BUCKET> \
  --dest <DEST_BUCKET> \
  --file <KEYS_FILE> \
  [OPTIONS]
```

**Parameters:**
- `--source, -s` (required): Source bucket name
- `--dest, -d` (required): Destination bucket name
- `--file, -f` (required): Path to text file containing object keys (one per line)
- `--part-size-mb` (optional): Part size in MB for multipart copy (min: 5, max: 5000, default: 500)
- `--max-retries` (optional): Maximum retry attempts per part (default: 3)

**Example:**
```bash
# Create a file with object keys to copy
cat > objects_to_copy.txt << EOF
documents/report-2025.pdf
images/photo1.jpg
videos/presentation.mp4
data/large-dataset.csv
EOF

# Copy objects
python -m s3.main multipart-copy \
  --source my-source-bucket \
  --dest my-dest-bucket \
  --file objects_to_copy.txt \
  --part-size-mb 1000 \
  --max-retries 5

# Expected output:
# ────────────────────────────────────────────────────────────
# Starting copy of 4 objects
# Source : s3://my-source-bucket
# Dest   : s3://my-dest-bucket
# ────────────────────────────────────────────────────────────
# 
# [1/4]
# Processing: documents/report-2025.pdf (0.05 GB, StorageClass: STANDARD)
#   ✅ Simple copy OK: documents/report-2025.pdf (StorageClass: STANDARD)
# 
# [2/4]
# Processing: images/photo1.jpg (0.02 GB, StorageClass: STANDARD)
#   ✅ Simple copy OK: images/photo1.jpg (StorageClass: STANDARD)
# 
# [3/4]
# Processing: videos/presentation.mp4 (3.50 GB, StorageClass: STANDARD)
#   ✅ Simple copy OK: videos/presentation.mp4 (StorageClass: STANDARD)
# 
# [4/4]
# Processing: data/large-dataset.csv (15.75 GB, StorageClass: INTELLIGENT_TIERING)
#   Multipart upload started — UploadId: AbCdEf123...
#   Uploading part 1 — range bytes=0-1048575999
#   Uploading part 2 — range bytes=1048576000-2097151999
#   ...
#   ✅ Multipart copy OK: data/large-dataset.csv (16 parts, StorageClass: INTELLIGENT_TIERING)
# 
# ────────────────────────────────────────────────────────────
# ✅ Success : 4/4
# Tutti gli oggetti sono stati copiati con successo!
```

**Retry Failed Objects:**
```bash
# If some objects failed, they are saved to failed_retry.txt
# Retry failed objects
python -m s3.main multipart-copy \
  --source my-source-bucket \
  --dest my-dest-bucket \
  --file failed_retry.txt
```

---

## Configuration Files

### Replication Configuration

Example: `replication_config.yaml`

```yaml
# Optional: Provide existing role ARN or let script create temp-replication role
# replication_role_arn: "arn:aws:iam::123456789012:role/MyReplicationRole"

# Global defaults (can be overridden per bucket)
default_dest_account_id: "987654321098"
default_change_ownership: true

# Default rule settings
rule_defaults:
  priority: 1
  status: "Enabled"
  storage_class: "INTELLIGENT_TIERING"
  delete_marker_replication: "Enabled"
  source_selection_criteria:
    ReplicaModifications:
      Status: "Enabled"

# Bucket configurations
buckets:
  - source_bucket: "prod-bucket-1"
    destination_bucket: "backup-bucket-1"
    # Inherits global defaults
    
  - source_bucket: "prod-bucket-2"
    destination_bucket: "backup-bucket-2"
    dest_account_id: "111222333444"  # Override for this bucket
    change_ownership: false
    rule_overrides:
      storage_class: "STANDARD"
      priority: 5
```

### Batch Operations Configuration

Example: `batch_operations_config.yaml`

```yaml
global_settings:
  account_id: "123456789012"
  role_arn: "arn:aws:iam::123456789012:role/S3BatchOperationsRole"
  report_bucket_arn: "arn:aws:s3:::my-reports-bucket"
  dest_canonical_id: "your-canonical-user-id-here"
  region: "eu-west-1"
  auto_start: true  # Automatically start jobs after creation

jobs:
  - source_bucket: "arn:aws:s3:::source-1"
    dest_bucket: "arn:aws:s3:::dest-1"
    report_prefix: "batch-reports/migration-1"
    
  - source_bucket: "arn:aws:s3:::source-2"
    dest_bucket: "arn:aws:s3:::dest-2"
    report_prefix: "batch-reports/migration-2"
```

### Bucket Policy Configuration

Example: `replica_bucket_policy_config.yaml`

```yaml
global_enable_replication: true
replication_role_arn: "arn:aws:iam::123456789012:role/ReplicationRole"
source_account_id: "123456789012"

# SIDs managed by this script
managed_sids:
  - "ReplicationPermissions"
  - "ReplicationOwnerOverride"

# Policy template (placeholders: {bucket_name}, {replication_role_arn}, {source_account_id})
policy_statements_template:
  - Sid: "ReplicationPermissions"
    Effect: "Allow"
    Principal:
      AWS: "{replication_role_arn}"
    Action:
      - "s3:ReplicateObject"
      - "s3:ReplicateDelete"
      - "s3:ReplicateTags"
      - "s3:GetObjectVersionTagging"
    Resource: "arn:aws:s3:::{bucket_name}/*"
    
  - Sid: "ReplicationOwnerOverride"
    Effect: "Allow"
    Principal:
      AWS: "{replication_role_arn}"
    Action: "s3:ObjectOwnerOverrideToBucketOwner"
    Resource: "arn:aws:s3:::{bucket_name}/*"

# Per-bucket configuration
buckets:
  backup-bucket-1:
    enable_replication: true
    
  backup-bucket-2:
    enable_replication: true
    
  temp-bucket:
    enable_replication: false  # Will remove replication policies
```

---

## Common Workflows

### Workflow 1: Setting Up Versioning and Inventory for Backup

```bash
# Step 1: Enable versioning on production buckets
python -m s3.main enable-versioning \
  --tag-key Environment \
  --tag-value production

# Step 2: Set up S3 inventory for tracking
python -m s3.main add-inventory-configuration \
  --destination-bucket inventory-reports-bucket \
  --tag-key Environment \
  --tag-value production \
  --prefix prod-inventory \
  --all-versions
```

### Workflow 2: Point-in-Time Recovery Setup

```bash
# Step 1: Enable versioning
python -m s3.main enable-versioning \
  --tag-key Backup \
  --tag-value pitr

# Step 2: Enable EventBridge notifications
python -m s3.main enable-notifications \
  --tag-key Backup \
  --tag-value pitr

# Step 3: Set up S3 inventory
python -m s3.main add-inventory-configuration \
  --destination-bucket pitr-inventory-bucket \
  --tag-key Backup \
  --tag-value pitr \
  --all-versions

# Step 4: When recovery is needed, run PITR
python -m s3.main pitr \
  --athena-database pitr_db \
  --athena-table s3_events \
  --s3-temp-bucket pitr-temp \
  --snapshot-end-time "2026-01-15T12:00:00Z" \
  --restore-iam-role-arn "arn:aws:iam::123456789012:role/PITRRole" \
  --batch-lambda-delete-arn "arn:aws:lambda:eu-west-1:123456789012:function:S3Delete" \
  --crawler-name pitr-crawler
```

### Workflow 3: Cross-Region Replication Setup

```bash
# Step 1: Create replication configuration file (replication_config.yaml)

# Step 2: Set up replication rules
python -m s3.main enable-replication \
  --config replication_config.yaml

# Step 3: Configure destination bucket policies
python -m s3.main manage-destination-policy \
  --config replica_bucket_policy_config.yaml

# Step 4: Verify replication (optional dry-run first)
python -m s3.main enable-replication \
  --config replication_config.yaml \
  --dry-run
```

### Workflow 4: Disaster Recovery - Restore Deleted Objects

```bash
# Check which buckets have versioning enabled
python -m s3.main check-buckets-versioning

# Restore all deleted objects in a specific bucket
python -m s3.main restore-all-deleted-objects critical-data-bucket
```

### Workflow 5: Large-Scale Object Migration

```bash
# Step 1: Create list of objects to copy
aws s3 ls s3://source-bucket/ --recursive | awk '{print $4}' > objects_to_copy.txt

# Step 2: Copy objects with multipart support
python -m s3.main multipart-copy \
  --source source-bucket \
  --dest dest-bucket \
  --file objects_to_copy.txt \
  --part-size-mb 1000

# Step 3: Retry any failed objects
python -m s3.main multipart-copy \
  --source source-bucket \
  --dest dest-bucket \
  --file failed_retry.txt
```

### Workflow 6: Cleanup Old Batch Operations

```bash
# Step 1: Check what would be cancelled (dry-run)
python -m s3.main clean-batch-operation-pending-jobs \
  --before-date 2025-12-01 \
  --dry-run \
  --verbose

# Step 2: Actually cancel the jobs
python -m s3.main clean-batch-operation-pending-jobs \
  --before-date 2025-12-01
```

---

## IAM Permissions Required

### Basic Operations
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketTagging",
        "s3:ListBucket",
        "s3:ListAllMyBuckets"
      ],
      "Resource": "*"
    }
  ]
}
```

### PITR Operations
```json
{
  "Effect": "Allow",
  "Action": [
    "athena:StartQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "glue:StartCrawler",
    "glue:GetCrawler",
    "s3control:CreateJob",
    "s3control:DescribeJob",
    "s3control:UpdateJobStatus"
  ],
  "Resource": "*"
}
```

### Replication Operations
```json
{
  "Effect": "Allow",
  "Action": [
    "iam:CreateRole",
    "iam:CreatePolicy",
    "iam:AttachRolePolicy",
    "iam:GetRole",
    "iam:DeleteRole",
    "iam:DeletePolicy",
    "s3:PutBucketReplication",
    "s3:GetBucketReplication",
    "s3:DeleteBucketReplication"
  ],
  "Resource": "*"
}
```

---

## Troubleshooting

### Versioning Not Enabling
- Ensure you have `s3:PutBucketVersioning` permission
- Check that bucket tags are correctly set
- Verify AWS credentials are configured

### PITR Queries Failing
- Ensure Glue crawler has completed successfully
- Verify Athena database and table names are correct
- Check S3 temp bucket has proper permissions

### Replication Not Working
- Verify IAM role has correct trust policy for S3 service
- Ensure destination bucket policy allows replication
- Check both source and destination buckets have versioning enabled

### Batch Operations Not Starting
- Verify IAM role has S3 Batch Operations permissions
- Check manifest file format is correct
- Ensure destination bucket ARN is valid

---

## Support

For issues, feature requests, or contributions, please visit:
- Repository: https://github.com/epsilonline/aws-scripts
- GitLab: https://gitlab.com/epsilonline/epsilon-internal/aws-script

---

## License

Maintained by Epsilon Line team.
