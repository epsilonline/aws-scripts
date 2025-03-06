import typer
from tf_import.utility import get_logger, tf_import_subprocess

logger = get_logger("TFI_SG_RULE")

TF_CMD = "terraform"

app = typer.Typer()


def check_if_value_is_in_array(name: str, value: any, values: list):
    if value not in values:
        logger.error(f"Parameter {name} can be only one of this value: {', '.join(values)}")
        exit(-1)


def check_if_value_is_in_range(name: str, value: any, min: int = 0, max: int = 65356):
    if value not in range(min, max):
        logger.error(f"Parameter {name} cannot in range {min}-{max}")
        exit(-1)


@app.command()
def import_sg_rule(security_group: str = typer.Option(...), terraform_resource_id: str = typer.Option(...),
                   rule_type: str = "ingress",
                   source_security_group: str = "", protocol: str = "tcp", start_port: int = 0,
                   end_port: int = 0, cidr: str = "", ipv6_cidr: str = "", import_default_egress: bool = False):
    import_string = f"{security_group}"
    """
    Import sg rule
    """
    if import_default_egress:
        import_string = f"{security_group}_egress_all_0_0_0.0.0.0/0_::/0"
    else:
        if source_security_group and (cidr or ipv6_cidr):
            logger.error("It is not possible to use the source_security_group parameter when using cidr and ipv6cidr")
            exit(-1)

        if not (source_security_group or cidr or ipv6_cidr):
            logger.error("At least one of the source_security_group, cidr or ipv6_cidr")
            exit(-1)

        check_if_value_is_in_array("rule_type", rule_type, ['ingress', 'egress'])
        import_string = "_".join([import_string, rule_type])

        check_if_value_is_in_array("protocol", protocol, ['all', 'tcp', 'udp'])
        import_string = "_".join([import_string, protocol])

        check_if_value_is_in_range("start_port", start_port)
        import_string = "_".join([import_string, str(start_port)])

        if start_port > 0 and end_port == 0:
            logger.info("Only start port provided")
            import_string = "_".join([import_string, str(start_port)])
        else:
            check_if_value_is_in_range("end_port", end_port)
            import_string = "_".join([import_string, str(end_port)])

        if source_security_group:
            import_string = "_".join([import_string, source_security_group])
        else:
            if cidr:
                import_string = "_".join([import_string, cidr])
            if ipv6_cidr:
                import_string = "_".join([import_string, ipv6_cidr])

    tf_import_subprocess(terraform_resource_id=terraform_resource_id, import_string=import_string)


if __name__ == "__main__":
    app()
