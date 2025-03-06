import typer

from route53.function import export_route53_zone


app = typer.Typer()

# Add commands here
app.command()(export_route53_zone)

if __name__ == "__main__":
    app()
