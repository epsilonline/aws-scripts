import typer

from s3.versioned_bucket import check_bucket_versioning

app = typer.Typer()

# Add commands here
app.command()(check_bucket_versioning)

if __name__ == "__main__":
    app()
