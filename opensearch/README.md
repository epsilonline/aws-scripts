# Opensearch

This script use aws identity for invoke opensearch APIs, ensure that you identity have right permission for invoke API and the host that you use can reach Opensearch deployed in VPC.

## Usage

```Bash
 aws-scripts opensearch --help
```
## Use this script collection for manage Opensearch Backup

### Requirements
To be able to perform any action you have to use an aws identity (iam user or iam role) that have these permissions:
```
{
  "Version": "2012-10-17",
  "Statement": [
      {
        "Sid": "EsAccess",
        "Effect": "Allow",
        "Action": "es:ESHttp*",
        "Resource": <opensearch domain>
      },
      {
        "Sid": "PassRole",
        "Effect": "Allow",
        "Action": "iam:PassRole",
        "Resource": <role with s3 bucket repository access>
      },
      {
        "Sid": "S3BucketList",
        "Action": "s3:ListBucket",
        "Effect": "Allow",
        "Resource": <bucket>
      },
      {
        "Sid": "S3Access",
        "Action": [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ],
        "Effect": "Allow",
        "Resource": <bucket>/*
      },
      {
        "Sid": "KMSDecrypt",
        "Action": [
          "kms:GenerateDataKey",
          "kms:Encrypt",
          "kms:Decrypt"
        ],
        "Effect": "Allow",
        "Resource": <kms key>
      }
  ]
}
```
Before run commands, ensure that you map the identity that use for run commands in Opensearch.
For more info read [official documentations](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ac.html).

### Enable backup
1) Register a new s3 repository on opensearch, in this repo you will find opensearch snapshots:
    ```Bash
    aws-script opensearch --host HOST register-s3-repository REPOSITORY_NAME BASE_PATH BUCKET_TO_REGISTER ROLE_ACCESS_TO_BUCKET
    ```

2) Manual create a snapshot:
    ```Bash
    aws-script opensearch --host HOST do-snapshot REPOSITORY_NAME SNAPSHOT_NAME
    ```
3) Check snapshot status
    ```Bash
    aws-script opensearch --host HOST get-snapshot-info REPOSITORY_NAME SNAPSHOT_NAME
    ```
4) Configure backup
    ```Bash
    aws-script opensearch --host HOST get-snapshot-info REPOSITORY_NAME SNAPSHOT_NAME
    ```
### Manage backup
#### Get the snapshot status:
```
aws-script opensearch --host HOST snapshot-status 
```
#### Perform a snapshot restore
```Bash
aws-script opensearch --host HOS restore-latest-snapshot REPOSITORY_NAME

# Restore latest snapshot

aws-script opensearch --host HOS restore-snapshot REPOSITORY_NAME
```
**NOTE**: By default executing this command will restore all indexes except dotted index, this is because due to special permissions on the OpenSearch Dashboards and fine-grained access control indexes, attempts to restore all indexes might fail, especially if you try to restore from an automated snapshot. 

#### To deregister a repository

```
aws-script opensearch --host HOST delete-repository REPOSITORY_NAME
```
N.B - Performing this action will not delete the s3 bucket used as repository, it will only delete the opensearch mapping for the specified repository