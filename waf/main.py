import typer

from waf.function import update_web_acl_for_all_distribution

app = typer.Typer()

# Add commands here
app.command()(update_web_acl_for_all_distribution)

if __name__ == "__main__":
    app()
