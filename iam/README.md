# IAM

## Descriptions

Helper script for AWS IAM.

## Available commands 

- **disable-all-access**: disable all access for user
- **disable-all-from-csv**: disable all credentials for user in csv list and if specify flag `--delete` delete user
- **disable-codecommit-credentials**: disable only codecommit credentials
- **disable-console-access**: disable only console access
- **disable-credentials**: disable only iam credentials
- **disable-ssh-public-keys**: disable only ssh key

All commands that support flag `--delete` first disable credentials and after delete credentials.

## Usage
```Bash
python3 main.py --help
```