import json
import logging
import os
import subprocess
from typing import List

TF_CMD = "terraform"
AWS_CMD = "aws --output json"


def get_logger(name, logging_level=None, date_fmt=None):
    logging_level = logging_level or 'debug' if os.environ.get("DEBUG", "false").lower() == "true" else 'info'
    #
    date_fmt = date_fmt or "%d/%m/%Y %H:%M:%s"

    levels = {
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    logging_level = levels.get(logging_level.lower(), logging.DEBUG)

    logger = logging.getLogger(name=name)
    logger.setLevel(logging_level)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging_level)

    # create formatter
    logging_format = "{date} %(name)s - %(levelname)s - %(message)s".format(date=" %(asctime)s -" if date_fmt else "")
    formatter = logging.Formatter(logging_format, datefmt=date_fmt)

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    # Child loggers propagate messages up to the handlers associated with their ancestor loggers, disable propagation to
    # avoid double print in cloudwatch
    logger.propagate = False

    return logger

logger = get_logger("UTILITY")


def tf_import_subprocess(terraform_resource_id: str, import_string: str):
    """
      Run terraform import as subprocess
    """

    logger.info("Run command: ")
    logger.info(" ".join([TF_CMD, 'import', f"'{terraform_resource_id}'", f"'{import_string}'"]))

    process = subprocess.Popen(" ".join([TF_CMD, 'import', f"'{terraform_resource_id}'", f"'{import_string}'"]),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()

    if stdout:
        logger.info(stdout.decode('utf-8'))
    if stderr:
        logger.error(stderr.decode('utf-8'))


def run_aws_command_subprocess(cmd: List[str]):
    """
      Run terraform import as subprocess
    """

    cmd = f"{AWS_CMD} {' '.join(cmd)}"
    logger.debug(f"Run command: {cmd}")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()

    out = stdout.decode('utf-8')
    if out:
        logger.debug(out)
    if stderr:
        logger.error(stderr.decode('utf-8'))

    return json.loads(out)


