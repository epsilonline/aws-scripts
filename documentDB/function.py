import logging
import boto3
from py_mongo_backup_restore import PyMongoBackupRestore
from pymongo import MongoClient
import csv
import tarfile
import os
import shutil
import requests
import typer

logging.basicConfig(level=logging.INFO, format="%(levelname)s : %(message)s")

def get_mongo_handler(profile, region, mongo_dst_host, pwd_ssm_path, cwd):
    try:
        session = boto3.Session(profile_name=profile)
        ssm = session.client('ssm', region_name=region)

        response = ssm.get_parameter(
            Name=pwd_ssm_path,
            WithDecryption=True
        )

        pwd = response['Parameter']['Value']
    except Exception as e:
        logging.error('Error during mongo password retrive : ' + e)
        raise SystemExit(1)

    try:
        if not os.path.exists(cwd + '/cert'):
            os.makedirs(cwd + '/cert')
            response = requests.get('https://truststore.pki.rds.amazonaws.com/' + region + '/' + region + '-bundle.pem')
            with open(cwd + "/cert/global-bundle.pem", mode="wb") as file:
                file.write(response.content)
    except Exception as e:
        logging.error('Error during mongo certificate download : ' + e)
        raise SystemExit(1)

    config = {
        'scheme': 'mongodb',
        'host': mongo_dst_host + ':27017',
        'username': 'docudbadmin',
        'password': pwd,
        'extra_options': '?tls=true&tlsCAFile=' + cwd + '%2Fcert%2Fglobal-bundle.pem&retryWrites=false',
    }

    mongo_handler = PyMongoBackupRestore(**config)
    try:
        mongo_handler.check_mongodump_mongorestore()  # Verifica se mongorestore è installato
    except Exception as e:
        logging.error('Mongotools are not present : ' + e)
        raise SystemExit(1)

    return mongo_handler


def create_user(client, users_file_path):
    try:
        with open(users_file_path, 'r') as file:
            csv_reader = csv.DictReader(file)

            for row in csv_reader:
                username = row['username']
                pwd = row['pwd']
                db = row['db']

                client.docdbadmin.command('createUser', username, pwd=pwd, roles=[{'role': 'readWrite', 'db': db}])
                logging.info('Utente ' + username + ' creato')

    except Exception as e:
        logging.error(e)
        raise SystemExit(1)


def get_dbs(dbs_file_path):
    dbs = {}

    try:
        with open(dbs_file_path, 'r') as file:
            csv_reader = csv.DictReader(file)

            for row in csv_reader:
                db_name = row['db_name']
                db_host = row['db_host']
                dbs[db_name] = db_host.replace('.', '_')
        return dbs
    except Exception as e:
        logging.error(e)
        raise SystemExit(1)


def get_backup_keys(client, bucket, dbs):
    keys = []

    response = client.list_objects_v2(
        Bucket=bucket
    )

    if response['KeyCount'] != 0:
        for item in response['Contents']:
            key = item['Key']
            for db in dbs:
                if db in key and dbs[db] in key:
                    keys.append(key)

        return keys
    else:
        logging.error('Bucket is empty')
        raise SystemExit(1)


def download_backups(client, bucket, dbs, cwd):
    # Lasciato per futura alberatura del bucket backup
    keys = get_backup_keys(client, bucket, dbs)

    for key in keys:
        client.download_file(bucket, key, cwd + '/dump.tar.gz')
        unzip_file = tarfile.open(cwd + '/dump.tar.gz')
        unzip_file.extractall(cwd + '/')
        unzip_file.close()
        os.remove(cwd + '/dump.tar.gz')


def get_backups_folder(profile, region, bucket, dbs, cwd):
    try:
        session = boto3.Session(profile_name=profile)
        s3 = session.client('s3', region_name=region)

        if not os.path.exists(cwd + '/dump'):

            download_backups(s3, bucket, dbs, cwd)
            logging.info('Dumps saved in ' + cwd + '/dump')
        else:
            answer = input('Database dumps already here, do you want to re download? (y, n) ')

            if answer != 'y' and answer != 'n':
                logging.error('Valore non valido')
                raise SystemExit(1)

            elif answer == 'y':
                shutil.rmtree(cwd + '/dump')
                download_backups(s3, bucket, dbs)
                logging.info('Dumps re downloaded in dump folder')

            elif answer == 'n':
                pass

    except Exception as e:
        logging.error(e)
        raise SystemExit(1)


def restore_database(mongo_handler, dbs, cwd):
    for db in dbs:
        try:
            mongo_handler.restore(
                database_name=db,  # Target Database Name
                backup_folder=cwd + '/dump/' + db,
            )
        except:
            logging.error('Errore durante il restore del database ' + db)


def create_users(profile: str = typer.Argument(..., help="AWS profile for auth"),
                 region: str = typer.Argument(..., help="AWS region for auth"),
                 host: str = typer.Argument(..., help="DocumentDB host"),
                 pwd_ssm_path: str = typer.Argument(..., help="DocumentDB password ssm path"),
                 users_file_path: str = typer.Argument(..., help="Csv file path that contains users to create")):
    mongo_handler = get_mongo_handler(profile, region, host, pwd_ssm_path)
    client = MongoClient(mongo_handler.get_uri())
    create_user(client, users_file_path)


def restore_dbs(profile: str = typer.Argument(..., help="AWS profile for auth"),
                region: str = typer.Argument(..., help="AWS region for auth"),
                host: str = typer.Argument(..., help="DocumentDB host"),
                pwd_ssm_path: str = typer.Argument(..., help="DocumentDB password ssm path"),
                backup_bucket: str = typer.Argument(..., help="Bucket where documentdb backups are stored"),
                dbs_file_path: str = typer.Argument(..., help="Csv file path that contains dbs to restore")):
    cwd = os.path.dirname(dbs_file_path)

    logging.info('Dump folder: ' + cwd + '/dump')
    logging.info('Certificate folder: ' + cwd + '/cert')

    mongo_handler = get_mongo_handler(profile, region, host, pwd_ssm_path, cwd)
    dbs = get_dbs(dbs_file_path)
    get_backups_folder(profile, region, backup_bucket, dbs, cwd)
    restore_database(mongo_handler, dbs, cwd)