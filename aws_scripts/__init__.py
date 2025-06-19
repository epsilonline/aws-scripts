import typer

# Import subcommands here
import tf_import
import opensearch
import ssm
import iam
import route53
import s3
import dynamodb
import backup
import cloudfront
import documentDB
import waf
from utils.aws import AWSHelper

app = typer.Typer(no_args_is_help=True, add_completion=True)

# Add sub commands here
app.add_typer(tf_import.app, name="tf-import")
app.add_typer(opensearch.app, name="opensearch")
app.add_typer(ssm.app, name="ssm")
app.add_typer(iam.app, name="iam")
app.add_typer(route53.app, name="route53")
app.add_typer(s3.app, name="s3")
app.add_typer(dynamodb.app, name="dynamodb")
app.add_typer(backup.app, name="backup")
app.add_typer(cloudfront.app, name="cloudfront")
app.add_typer(documentDB.app, name="documentDB")
app.add_typer(waf.app, name="waf")


@app.callback()
def main(profile: str = None):
    """

    """
    profile = profile or 'default'
    typer.secho(f"\nConfiguring CLI for use profile: '{profile or 'default'}'")
    AWSHelper.configure(profile=profile)


if __name__ == "__main__":
    app()
