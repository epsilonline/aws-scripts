import typer

from iam.disable_iam import (disable_credentials, disable_codecommit_credentials, disable_console_access,
                        disable_ssh_public_keys, disable_all_access, disable_all_from_csv)

app = typer.Typer()

# Add commands here
app.command()(disable_credentials)
app.command()(disable_codecommit_credentials)
app.command()(disable_console_access)
app.command()(disable_ssh_public_keys)
app.command()(disable_all_access)
app.command()(disable_all_from_csv)

if __name__ == "__main__":
    app()
