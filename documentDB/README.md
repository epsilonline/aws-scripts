# AWS DOCUMENTDB

## Descriptions

Helper script for AWS documentDB.

## Available commands

- **copy-from-table**: This script will start aws backup jobs
- **import-data-from-csv**: import data from csv

## Usage
```Bash
python3 main.py --help
```


DocumentDB create users/restore database script

1) Create users
```
WARNING:
To be able to create any user, users.csv must be created in data folder and filled up like the sample

Execute: ./install.sh

documentdb-restore create-users <profile> <region> <mongo host> <mongo pwd ssm path>
```
2) Restore database
```
WARNING:
To be able to restore any database, dbs.csv must be created in data folder and filled up like the sample
N.B "db_host" field is the source cluster host

Execute: ./install.sh

documentdb-restore restore-dbs <profile> <region> <mongo host> <mongo pwd ssm path> <backup bucket name>
```