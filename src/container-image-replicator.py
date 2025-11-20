#!/usr/bin/env python3.11
import argparse
import logging
from pathlib import Path
from sys import exit
from sys import stdout
from typing import Any
from typing import Dict

import coloredlogs
import docker
import verboselogs
import yaml
from typing_extensions import LiteralString

from build import construct_build
from build import parse_image_list_build
from replicate import parse_image_list_replicate
from replicate import replicate

# mypy: disable-error-code = attr-defined
verboselogs.install()
logger = logging.getLogger(__name__)


def init_docker() -> Any | Any:
    """initialize docker connection

    Returns:
        Any | Any: client and API objects
    """
    docker_client: object = docker.from_env()
    docker_api: object = docker.APIClient()
    return docker_client, docker_api


def init_arg_parser() -> Any:
    """parses CLI args

    Returns:
        Any: parsed arguments object
    """
    try:
        parser = argparse.ArgumentParser(
            description="description: make copies of container images from one registry to another",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="container-image-replicator",
        )

        args_optional = parser.add_argument_group("optional")
        args_required = parser.add_argument_group("required")

        args_optional.add_argument("--version", "-v", action="version", version="v0.12.0")

        args_optional.add_argument(
            "--max-workers",
            action="store",
            default=2,
            dest="max_workers",
            help="maximum number of worker threads to execute at any one time. One thread per container image",
            type=int,
        )

        args_optional.add_argument(
            "--log-level",
            action="store",
            default="INFO",
            dest="log_level",
            help="set logging level (INFO, ERROR, DEBUG)",
        )

        args_optional.add_argument(
            "--force-pull-push",
            action="store_true",
            default=False,
            dest="force_pull_push",
            help="don't check destination or local image cache and pull and push.\
                Useful for mutable tags. Be careful, as this can hit rate limits quickly!",
        )

        args_optional.add_argument(
            "--no-color",
            "--no-colors",
            action="store_true",
            default=False,
            dest="no_colors",
            help="disable color output from the logger",
        )

        args_required.add_argument("input_file", action="store", help="path to YAML file containing registry information", type=Path)

        arguments = parser.parse_args()
        return arguments
    except argparse.ArgumentError:
        logging.fatal("failed to parse arguments")
        exit(1)


def parse_image_list_yaml(image_list: Dict[LiteralString, Any]) -> tuple[list[Any], list[Any]]:
    """searches for each element in the list for all expected keys/values

    Args:
        image_list (Dict[LiteralString, Any]): list of images from input YAML

    Returns:
        bool: True if the whole file parsed as expected
    """
    build_list = list()
    replicate_list = list()
    try:
        for image in image_list["images"]:
            try:
                if isinstance(image["build"], dict):
                    parse_image_list_build(logger, image)
                    build_list.append(image)
            except KeyError:
                pass
            try:
                if isinstance(image["source"], dict):
                    parse_image_list_replicate(logger, image)
                    replicate_list.append(image)
            except KeyError:
                pass
    except KeyError as e:
        logger.critical(f"syntax error in list file provided:\n{e}")
        exit(1)
    logger.success("input file successfully validated")
    return build_list, replicate_list


def main(docker_api: object) -> None:
    """main

    Args:
        docker_api (object): api object
    """
    arguments = init_arg_parser()

    if arguments.log_level == "INFO":
        log_level = "INFO"
    elif arguments.log_level == "ERROR":
        log_level = "ERROR"
    elif arguments.log_level == "DEBUG":
        log_level = "DEBUG"
    else:
        logging.error("failed to determine the specified value for --log-level")

    if arguments.no_colors:
        logging.basicConfig(
            level=eval(f"logging.{log_level}"),
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            stream=stdout,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    else:
        coloredlogs.install(level=log_level, fmt="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")

    try:
        image_list = yaml.safe_load(Path(arguments.input_file).read_text())
        build_list, replicate_list = parse_image_list_yaml(image_list)

        # store the lengths of the two main as we will do multiple int comparisons
        build_list_length = len(build_list)
        replicate_list_length = len(replicate_list)

        # is there anything to do?
        if (build_list_length > 0) or (replicate_list_length > 0):
            if build_list_length > 0:
                construct_build(logger, arguments, docker_client, build_list)
            if replicate_list_length > 0:
                replicate(logger, arguments, docker_api, docker_client, replicate_list)
        else:
            logger.warning("no actions found that need taking... strange")
    except FileNotFoundError:
        logger.critical(f"input file not found. Cannot continue: {Path(arguments.input_file)}")
    except yaml.parser.ParserError as e:
        logger.critical(f"failed to parse input file: {Path(arguments.input_file)} with error: {e}")


if __name__ == "__main__":
    try:
        docker_client, docker_api = init_docker()
        main(docker_api)
        docker_client.close()
    except docker.errors.DockerException:
        print("Error: Unable to communicate with docker daemon")
    except KeyboardInterrupt:
        docker_client.close()
        exit(1)
