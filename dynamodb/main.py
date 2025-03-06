import typer

from dynamodb.function import import_data_from_csv, copy_from_table

app = typer.Typer()

# Add commands here
app.command()(import_data_from_csv)
app.command()(copy_from_table)

if __name__ == "__main__":
    app()
