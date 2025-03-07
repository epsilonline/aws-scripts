import typer

from cloudfront.function import (update_all_cdns, update_cdn_with_json, revert_update_all_cdns,
                                 update_all_cdns_tls_version, maintenance_mode_to_all_distribution)

app = typer.Typer()

# Add commands here
app.command()(update_all_cdns)
app.command()(update_cdn_with_json)
app.command()(revert_update_all_cdns)
app.command()(update_all_cdns_tls_version)
app.command()(maintenance_mode_to_all_distribution)

if __name__ == "__main__":
    app()
