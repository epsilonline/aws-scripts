import typer

from ssm.function import find_parameters

app = typer.Typer()

app.command()(find_parameters)

if __name__ == "__main__":
    app()
