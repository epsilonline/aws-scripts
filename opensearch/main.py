import os
from typing import Annotated

import typer

from opensearch.commands import (delete_repository, get_snapshot_info, do_snapshot,
                                 snapshot_status, register_s3_repository, snapshot_list, get_latest_snapshot,
                                 restore_latest_snapshot, restore_snapshot, create_snapshot_policy)
from security.cloudfront.insecure_oai import logger


def callback(host: Annotated[str, typer.Option()], profile: str = None, region: str = None):
    if not host:
        logger.error("host it's required")
        exit(-1)
    os.environ['HOST'] = host
    os.environ['AWS_PROFILE'] = profile or 'default'
    if region:
        os.environ['AWS_REGION'] = region


app = typer.Typer(callback=callback)

app.command()(register_s3_repository)
app.command()(do_snapshot)
app.command()(snapshot_status)
app.command()(get_snapshot_info)
app.command()(restore_snapshot)
app.command()(delete_repository)
app.command()(snapshot_list)
app.command()(get_latest_snapshot)
app.command()(restore_latest_snapshot)
app.command()(create_snapshot_policy)

if __name__ == "__main__":
    app()
