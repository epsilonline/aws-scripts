import typer
from opensearch.function import *


def register_s3_repository(repository_name: str = typer.Argument(..., help="S3 repo name"),
                           base_path: str = typer.Argument(..., help="S3 repo path"),
                           bucket_to_register: str = typer.Argument(..., help="Opensearch host"),
                           role_access_to_bucket: str = typer.Argument(..., help="Opensearch host")):
    auth = aws_auth()
    register_repository(auth, os.environ['HOST'], repository_name, base_path, bucket_to_register, role_access_to_bucket)


def do_snapshot(repository_name: str = typer.Argument(..., help="Opensearch repo name"),
                snapshot_name: str = typer.Argument(..., help="Opensearch snapshot name")):
    auth = aws_auth()
    trigger_snapshot(auth, os.environ['HOST'], repository_name, snapshot_name)


def snapshot_status():
    auth = aws_auth()
    snapshot_status_cmd(auth, os.environ['HOST'])


def get_snapshot_info(repository_name: str = typer.Argument(..., help="Opensearch repo name"),
                      snapshot_name: str = typer.Argument(..., help="Opensearch snapshot name")):
    auth = aws_auth()
    snapshot_info_cmd(auth, os.environ['HOST'], repository_name=repository_name, snapshot_name=snapshot_name)


def delete_repository(repository_name: str = typer.Argument(..., help="Opensearch repo name")):
    auth = aws_auth()
    deregister_repository(auth, os.environ['HOST'], repository_name)


def snapshot_list(repository_name: str = typer.Argument(..., help="Opensearch repo name")):
    auth = aws_auth()
    snapshot_list_cmd(auth, os.environ['HOST'], repository_name)


def get_latest_snapshot(repository_name: str = typer.Argument(..., help="Opensearch repo name")):
    auth = aws_auth()
    get_latest_snapshot_cmd(auth, os.environ['HOST'], repository=repository_name)


def restore_latest_snapshot(repository_name: str = typer.Argument(..., help="Opensearch repo name"),
                            skip_restore_of_hidden_index: bool = typer.Argument(True,
                                                                                help="If true skip restore of hidden index")):
    auth = aws_auth()
    restore_latest_snapshot_cmd(auth, os.environ['HOST'], repository_name, skip_restore_of_hidden_index)


def restore_snapshot(repository_name: str = typer.Argument(..., help="Opensearch repo name"),
                     snapshot_name: str = typer.Argument(..., help="Opensearch snapshot name"),
                     skip_restore_of_hidden_index: bool = typer.Argument(True,
                                                                         help="If true skip restore of hidden index")):
    auth = aws_auth()
    restore_snapshot_cmd(auth, os.environ['HOST'], repository_name=repository_name, snapshot_name=snapshot_name,
                         skip_restore_of_hidden_index=skip_restore_of_hidden_index)


def create_snapshot_policy(repository_name: str = typer.Argument(..., help="Opensearch repo name"),
                           policy_name: str = typer.Argument(..., help="Policy name"),
                           schedule_expression: str = typer.Argument(..., help="Schedule expression"),
                           timezone: str = typer.Argument("UTC", help="Timezone"),
                           ):
    auth = aws_auth()
    create_snapshot_policy(auth, os.environ['HOST'], policy_name=policy_name, repository_name=repository_name,
                           schedule_expression=schedule_expression, timezone=timezone)
