import typer

from documentDB.function import create_users, restore_dbs

app = typer.Typer()

# Add commands here
app.command()(create_users)
app.command()(restore_dbs)

if __name__ == "__main__":
    app()
