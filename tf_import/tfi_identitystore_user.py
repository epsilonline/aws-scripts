import pathlib

import typer
from tf_import.utility import get_logger, tf_import_subprocess, run_aws_command_subprocess
import csv
from time import sleep

logger = get_logger('TFI_IDENTITY_STORE')

TF_CMD = "terraform"

app = typer.Typer()


@app.command()
def import_identity_store_user(identity_store_id: str, user_id: str = "",
                               terraform_resource_id: str = typer.Option(...)):

    import_string = f"{identity_store_id}/{user_id}"
    """
      Import sg rule
    """

    tf_import_subprocess(terraform_resource_id=terraform_resource_id, import_string=import_string)


@app.command()
def import_identity_store_user_from_csv(identity_store_id: str, csv_file: str = typer.Option(...),
                                        terraform_resource_id: str = typer.Option(...),
                                        username_column: int = 0, delimiter: str = ','):
    get_user_info_cmd = f"identitystore list-users --identity-store-id {identity_store_id} --filters AttributePath=UserName,AttributeValue="

    import_string = "{identity_store_id}/{user_id}"

    """
      Import sso user from csv 
    """
    csv_file_path = pathlib.Path(csv_file)

    with open(csv_file_path, newline='') as csvfile:
        rows = csv.reader(csvfile, delimiter=delimiter, )
        next(csvfile)
        for row in rows:
            username = row[username_column]
            user_info = run_aws_command_subprocess([get_user_info_cmd + f"\"{username}\""])
            try:
                user_id = user_info['Users'][0]['UserId']
                tmp_import_string = import_string.format(identity_store_id=identity_store_id, user_id=user_id)
                tf_import_subprocess(terraform_resource_id=f"{terraform_resource_id}[\"{username}\"]",
                                     import_string=tmp_import_string)
            except (IndexError, KeyError):
                logger.error("User not found")

    # tf_import_subprocess(terraform_resource_id=terraform_resource_id, import_string=import_string)


@app.command()
def import_identity_store_group_membership_from_csv(identity_store_id: str, group_id: str, csv_file: str = typer.Option(...),
                                              terraform_resource_id: str = typer.Option(...),
                                              username_column: int = 0, delimiter: str = ','):
    get_user_info_cmd = (f"identitystore list-users --identity-store-id {identity_store_id} "
                         f"--filters AttributePath=UserName,AttributeValue=")
    list_group_memberships_cmd = f"identitystore list-group-memberships --identity-store-id {identity_store_id} --group-id {group_id}"

    group_memberships = run_aws_command_subprocess([list_group_memberships_cmd])['GroupMemberships']
    import_string = "{identity_store_id}/{membership_id}"

    """
      Import sso user from csv 
    """
    csv_file_path = pathlib.Path(csv_file)
    with open(csv_file_path, newline='') as csvfile:
        rows = csv.reader(csvfile, delimiter=delimiter, )
        next(csvfile)
        for row in rows:
            username = row[username_column]
            user_info = run_aws_command_subprocess([get_user_info_cmd + f"\"{username}\""])
            sleep(1)
            try:
                user_id = user_info['Users'][0]['UserId']
                m = list(filter(lambda x: x['MemberId'].get('UserId', '') == user_id, group_memberships))
                if m:
                    m = m[0]
                    membership_id = m['MembershipId']
                    if membership_id:
                        tmp_import_string = import_string.format(identity_store_id=identity_store_id, membership_id=membership_id)
                        print(tmp_import_string)
                        tf_import_subprocess(terraform_resource_id=f"{terraform_resource_id}[\"{username}\"]",
                                            import_string=tmp_import_string)
            except (IndexError, KeyError):
                logger.error("User or MembershipId not found")

    # tf_import_subprocess(terraform_resource_id=terraform_resource_id, import_string=import_string)


if __name__ == "__main__":
    app()
