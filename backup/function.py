import csv
import boto3
import logging
import typer

logging.basicConfig(level=logging.INFO, format="%(levelname)s : %(message)s")


def get_resources(file_path):
    resources = {}

    with open(file_path, 'r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            source_resource = row['source_resource']
            dst_resource = row['dst_resource']
            resources[source_resource] = dst_resource
    return resources


def get_key_manager(client, kms):
    response = client.describe_key(
        KeyId=kms
    )

    key_manager = response['KeyMetadata']['KeyManager']
    return key_manager


def list_recovery_points_by_backup_vault(session, region, vault_arn, source_resource):
    backup = session.client('backup', region_name=region)
    paginator = backup.get_paginator('list_recovery_points_by_backup_vault')
    page_iterator = paginator.paginate(BackupVaultName=vault_arn)
    filtered_iterator = page_iterator.search(
        f'RecoveryPoints[?Status == `COMPLETED`] && RecoveryPoints[?ResourceName == `{source_resource}`] | [0]')

    return list(filtered_iterator)


def get_metadata(session, region, vault_name, recovery_point_arn, target_name, kms_key_arn):
    # kms_key_arn è la chiave che cripta il vault, 
    # ho assunto che se è utilizzata una customer kms
    # sarà utilizzata anche per criptare il vault utilizzato

    supported_services = ['S3', 'DynamoDB', 'EFS']
    backup = session.client('backup', region_name=region)

    metadata = backup.get_recovery_point_restore_metadata(
        BackupVaultName=vault_name,
        RecoveryPointArn=recovery_point_arn
    )

    service = metadata['ResourceType']

    if service in supported_services:

        restore_metadata = metadata['RestoreMetadata']

        match service:
            case 'DynamoDB':
                restore_metadata['targetTableName'] = target_name

                if kms_key_arn != '':
                    kms = session.client('kms', region_name=region)
                    key_manager = get_key_manager(kms, kms_key_arn)

                    if key_manager == 'CUSTOMER':
                        restore_metadata['encryptionType'] = 'KMS'
                        restore_metadata['kmsMasterKeyArn'] = kms_key_arn
                    else:
                        restore_metadata['encryptionType'] = 'KMS'
                else:
                    restore_metadata['encryptionType'] = 'Default'

                logging.info(restore_metadata)
                return restore_metadata

            case 'EFS':

                restore_metadata['newFileSystem'] = 'false'
                restore_metadata['file-system-id'] = target_name

                if kms_key_arn != '':
                    kms = session.client('kms', region_name=region)
                    key_manager = get_key_manager(kms, kms_key_arn)

                    if key_manager == 'CUSTOMER':
                        restore_metadata['Encrypted'] = 'true'
                        restore_metadata['KmsKeyId'] = kms_key_arn
                    else:
                        restore_metadata['Encrypted'] = 'true'
                else:
                    restore_metadata['Encrypted'] = 'false'

                logging.info(restore_metadata)
                return restore_metadata

            case 'S3':

                restore_metadata['DestinationBucketName'] = target_name
                restore_metadata['NewBucket'] = 'false'
                restore_metadata['CreationToken'] = 'bucket-restore'

                if kms_key_arn != '':
                    kms = session.client('kms', region_name=region)
                    key_manager = get_key_manager(kms, kms_key_arn)

                    if key_manager == 'CUSTOMER':
                        restore_metadata['Encrypted'] = 'true'
                        restore_metadata['EncryptionType'] = 'SSE-KMS'
                        restore_metadata['KMSKey'] = kms_key_arn
                    else:
                        restore_metadata['Encrypted'] = 'true'
                        restore_metadata['EncryptionType'] = 'SSE-S3'
                else:
                    restore_metadata['Encrypted'] = 'false'

                logging.info(restore_metadata)
                return restore_metadata
    else:
        logging.error('Trying to restore unsupported service')
        raise SystemExit(1)


def start_restore_job(session, region, vault_name, recovery_point_arn, backup_role, target_name, kms_key_arn=''):
    backup = session.client('backup', region_name=region)

    restore_metadata = get_metadata(session, region, vault_name, recovery_point_arn, target_name, kms_key_arn)

    response = backup.start_restore_job(
        RecoveryPointArn=recovery_point_arn,
        Metadata=restore_metadata,
        IamRoleArn=backup_role
    )

    restore_job_id = response['RestoreJobId']

    restore_job_metadata = backup.describe_restore_job(
        RestoreJobId=restore_job_id
    )

    restore_job_state = restore_job_metadata['Status']

    logging.info('RESTORE JOB STATUS : ' + restore_job_state)


def launch_restore_jobs(profile, region, vault_name, file_path):
    session = boto3.Session(profile_name=profile)

    resources = get_resources(file_path)

    for resource in resources:
        filtered_iterator = list_recovery_points_by_backup_vault(session, region, vault_name, resource)
        if len(filtered_iterator) > 0:
            for key_data in filtered_iterator:
                vault = key_data['BackupVaultName']
                recovery_point = key_data['RecoveryPointArn']
                restore_role_arn = key_data['IamRoleArn']
                is_encrypted = key_data['IsEncrypted']
                if is_encrypted:
                    key = key_data['EncryptionKeyArn']
                    start_restore_job(session, region, vault, recovery_point, restore_role_arn, resources[resource], key)
                else:
                    start_restore_job(session, region, vault, recovery_point, restore_role_arn, resources[resource])
        else:
            logging.error(
                'La risorsa ' + resource + 'non è presente nel csv file oppure non ci sono recovery point disponibili')

def start_restore_jobs(profile: str = typer.Argument(..., help="AWS profile for auth"),
                       region: str = typer.Argument(..., help="AWS region for auth"),
                       vault_name: str = typer.Argument(..., help="Backups vault name"),
                       file_path: str = typer.Argument(..., help="Csv file path that contains source and destination resource names that have to be restored")):
    launch_restore_jobs(profile, region, vault_name, file_path)
