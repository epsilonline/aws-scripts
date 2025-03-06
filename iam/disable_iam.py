import boto3
import typer
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
iam_client = boto3.client("iam")


def disable_credentials(username: str, delete: bool = False):
    access_keys = iam_client.list_access_keys(UserName=username)
    for access_key in access_keys.get("AccessKeyMetadata", []):
        iam_client.update_access_key(UserName=username, AccessKeyId=access_key["AccessKeyId"], Status="Inactive")
        if delete:
            iam_client.delete_access_key(UserName=username, AccessKeyId=access_key["AccessKeyId"])
    logger.info(f"[{username}]: Credentials %s", "deleted" if delete else "disabled")


def disable_ssh_public_keys(username: str, delete: bool = False):
    public_keys = iam_client.list_ssh_public_keys(UserName=username)
    for public_key in public_keys.get("SSHPublicKeys", []):
        iam_client.update_ssh_public_key(UserName=username,
                                         SSHPublicKeyId=public_key["SSHPublicKeyId"],
                                         Status="Inactive")
        if delete:
            iam_client.delete_ssh_public_key(UserName=username,
                                              SSHPublicKeyId=public_key["SSHPublicKeyId"])
    logger.info(f"[{username}]: Public keys %s", "deleted" if delete else "disabled")


def disable_codecommit_credentials(username: str, delete: bool = False):
    codecommit_credentials = iam_client.list_service_specific_credentials(UserName=username,
                                                                          ServiceName='codecommit.amazonaws.com')
    for codecommit_credential in codecommit_credentials.get("ServiceSpecificCredentials", []):
        iam_client.update_service_specific_credential(UserName=username, ServiceSpecificCredentialId=
                                                      codecommit_credential["ServiceSpecificCredentialId"],
                                                      Status="Inactive")
        if delete:
            iam_client.delete_service_specific_credential(UserName=username, ServiceSpecificCredentialId=
                                                          codecommit_credential["ServiceSpecificCredentialId"])
    logger.info(f"[{username}]: Codecommit credentials %s", "deleted" if delete else "disabled")


def disable_console_access(username: str):
    try:
        iam_client.delete_login_profile(UserName=username)
    except iam_client.exceptions.NoSuchEntityException:
        # login access it's already disabled
        pass
    logger.info(f"[{username}]: Console access disabled")


def _delete_user(username: str):
    iam_client.delete_user(UserName=username)
    logger.info(f"[{username}]: Deleted")


def disable_all_access(username: str):
    disable_credentials(username)
    disable_ssh_public_keys(username)
    disable_codecommit_credentials(username)
    disable_console_access(username)


def detach_policies(username: str):
    paginator = iam_client.get_paginator('list_attached_user_policies')
    for response in paginator.paginate(UserName=username):
        for policy in response['AttachedPolicies']:
            policy_name =policy['PolicyName']
            policy_arn = policy['PolicyArn']
            logger.info(f"[{username}] - Remove policy {policy_name}")
            iam_client.detach_user_policy(UserName=username, PolicyArn=policy_arn)

    inline_policies = iam_client.list_user_policies(UserName=username)['PolicyNames']
    for policy_name in inline_policies:
        logger.info(f"[{username}] - Remove policy {policy_name}")
        iam_client.delete_user_policy(UserName=username, PolicyName=policy_name)

    logger.info(f"[{username}]: All policies detached")


def delete_from_groups(username: str):
    paginator = iam_client.get_paginator('list_groups_for_user')
    for response in paginator.paginate(UserName=username):
        for group in response['Groups']:
            group_name = group['GroupName']
            logger.info(f"[{username}] Remove from group {group_name}")
            iam_client.remove_user_from_group(UserName=username, GroupName=group_name)


def delete_mfa_devices(username: str, delete: bool = False):
    response = iam_client.list_mfa_devices(UserName=username)
    mfa_devices = response.get('MFADevices', [])

    # Iterate through the devices and delete them
    for device in mfa_devices:
        serial_number = device['SerialNumber']
        logger.info(f"[{username}]: Deactivating virtual MFA device: {serial_number}")

        # Deactivate the MFA device
        iam_client.deactivate_mfa_device(UserName=username, SerialNumber=serial_number)

        # If it's a virtual MFA device, delete it
        if "mfa/" in serial_number and delete:  # Virtual MFA devices have "mfa/" in their ARN
            logger.info(f"[{username}]: Deleting virtual MFA device: {serial_number}")
            iam_client.delete_virtual_mfa_device(SerialNumber=serial_number)

    logger.info(f"[{username}]: All MFA devices deleted ")


def disable_all_from_csv(user_list_csv: str, delete_user: bool = False, debug: bool = False):
    if debug:
        logger.setLevel(logging.DEBUG)
    user_list_csv = Path(user_list_csv)
    if user_list_csv.exists():
        with open(user_list_csv, newline='') as csvfile:
            reader = csv.DictReader(csvfile, quotechar='"')
            user_key = [x for x in reader.fieldnames if x in ['user', 'username']]
            if len(user_key) == 1:
                user_key = user_key[0]
            else:
                logger.error("Ensure that input csv file have 'user' or 'username' field.")
                exit(-1)
            for row in reader:
                try:
                    username = row[user_key]
                    logger.info(f"[{username}]: Console access disabled")
                    disable_credentials(username, delete_user)
                    disable_console_access(username)
                    disable_ssh_public_keys(username, delete_user)
                    disable_codecommit_credentials(username, delete_user)
                    delete_mfa_devices(username, delete_user)
                    if delete_user:
                        detach_policies(username)
                        delete_from_groups(username)
                        _delete_user(username)
                except Exception as e:
                    logger.error(f"[{username}]: Error occured skip delete")
                    logger.debug(e)
    else:
        logger.info(f"Input {user_list_csv} file not found.")


if __name__ == "__main__":
    typer.run(disable_all_from_csv)
