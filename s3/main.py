import typer

from s3.versioned_bucket import check_bucket_versioning
from s3.pitr import pitr

app = typer.Typer()

# Add commands here
app.command()(check_bucket_versioning)
app.command()(pitr)

if __name__ == "__main__":
    app()
