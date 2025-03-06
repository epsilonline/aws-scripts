import typer

from backup.function import launch_restore_jobs

app = typer.Typer()

# Add commands here
app.command()(launch_restore_jobs)

if __name__ == "__main__":
    app()
