import typer

from tf_import.tfi_sg_rule import import_sg_rule
from tf_import.tfi_identitystore_user import (import_identity_store_user, import_identity_store_user_from_csv,
                                              import_identity_store_group_membership_from_csv)

app = typer.Typer()

# Add commands here
app.command()(import_sg_rule)
app.command()(import_identity_store_user)
app.command()(import_identity_store_user_from_csv)
app.command()(import_identity_store_group_membership_from_csv)

if __name__ == "__main__":
    app()
