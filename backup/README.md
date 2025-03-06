# AWS BACKUP

## Descriptions

Helper script for AWS Backup.

## Available commands

- **launch-restore-jobs**: This script will start aws backup jobs

## Usage
```Bash
python3 main.py --help
```


###  launch-restore-jobs

1) Create a csv file named `resources.csv`, fill it with many resource names as you want to restore. You can take 'sample_resources.csv' as exemple file to use.
2) Once the csv file has been created run:
```
 aws-scripts backup launch-restore-jobs <aws profile> <aws region> <aws backup vault name>
```