<div align="center">

  <img src="img/logo.png" alt="logo" width="140" height="auto" />
  <br/>

  <h3><b>AWS Scripts</b></h3>
  <p>A comprehensive CLI collection of helper scripts to manage, secure, and automate AWS resources.</p>

</div>

---

## 🚀 Features Overview

`aws-scripts` provides a unified interface to streamline AWS operations:

- **Automation**: Efficiently handle bulk tasks and resource management.
- **Security Audits**: Perform automated security checks and compliance enforcement.
- **Backups**: Simplified snapshot and restoration workflows across services.
- **Migrations**: Automated transitions between resource configurations (e.g., GP2 to GP3).

---

## 🛠 Prerequisites & Installation

### Prerequisites
- **Python 3.10+**

### Installation
The project includes an `install.sh` script to handle dependencies automatically using `poetry` and `pipx`.

```bash
./install.sh
```

---

## 💻 Global Usage

The CLI follows a standard syntax for all modules:

```bash
aws-scripts <module> <command> [OPTIONS]
```

Global configurations (such as AWS Profile and Region) are handled automatically by the `AWSHelper` utility. You can specify these via common flags:

```bash
aws-scripts s3 versioning --profile my-profile --region eu-central-1
```

---

## 📦 Modules Directory

| Module | Primary Capabilities |
| :--- | :--- |
| **S3** | Versioning, EventBridge, Inventory, PITR, Cross-region replication, Batch Ops, Multipart copy. |
| **EC2** | Snapshot & volume cleanup, IMDSv2 bulk updates, GP2 to GP3 migration. |
| **DynamoDB** | CSV data imports, table-to-table data copying. |
| **DocumentDB** | Bulk user creation, restoration from S3 backups. |
| **CloudFront** | Distribution origin updates, TLS enforcement, maintenance mode, OAI security checks. |
| **IAM** | Automated offboarding (keys, console, MFA, CodeCommit). |
| **OpenSearch** | Snapshot lifecycle management (register S3 repo, trigger, restore, policies). |
| **Route53** | Export DNS zones to standard files. |
| **SSM** | Bulk Parameter Store searching by prefix and value. |
| **WAF** | Bulk WebACL assignments for CloudFront. |
| **Backup** | Execute restore jobs from CSV lists. |
| **ECR** | Force image replication across registries. |
| **Security** | Manage and remove SSO user assignments. |
| **Terraform (tfi)** | Automated imports (SG rules, Identity Store users/groups). |

---

## 🤝 Contributing

### How to Add a New Module

1. **Create a folder** under the root directory.
2. **Implement `main.py`** using the `Typer` library to define your CLI commands.
3. **Register the module** in `aws_scripts/__init__.py` to integrate it into the main CLI entry point.

### Authors (Epsilon Team)

- **Luigi Pellecchia**: [@luigi.pellecchia](https://gitlab.com/lu_pe)
- **Alessandro Falcone**: [@alessandro.falcone](https://gitlab.com/alessandro.falcone)
- **Stefano Marsiglia**: [@stefano.marseglia](https://gitlab.com/stefano.marseglia)
- **Claudio Perrotta**: [@claudio.perrotta](https://gitlab.com/claudio.perrotta)
- **Gabriele Previtera**: [@jiin995](https://gitlab.com/jiin995)
- **Pino Villano**: [@pino.villano](https://gitlab.com/pino.villano)