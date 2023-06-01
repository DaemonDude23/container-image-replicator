#!/usr/bin/env python3
import argparse
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from pathlib import Path
from sys import stdout
from time import sleep
from typing import Any
from typing import Tuple

import coloredlogs
import docker
import verboselogs
import yaml


verboselogs.install()
logger = logging.getLogger(__name__)


def init_docker() -> Any | Any:
    docker_client = docker.from_env()
    docker_api = docker.APIClient()
    return docker_client, docker_api


def init_arg_parser() -> Any:
    try:
        parser = argparse.ArgumentParser(
            description="description: make copies of container images from one registry to another",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="container-image-replicator",
        )

        args_optional = parser.add_argument_group("optional")
        args_required = parser.add_argument_group("required")

        args_optional.add_argument("--version", "-v", action="version", version="v0.8.0")

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
        print("failed to parse arguments")
        exit(1)


# def parse_image_list_yaml(image_list: Dict[LiteralString, Any]) -> bool:
def parse_image_list_yaml(image_list) -> bool:
    """searches for each element in the list for all expected keys/values

    Args:
        image_list (str): list of images from input YAML

    Returns:
        bool: True
    """
    try:
        for image in image_list["images"]:
            str(image["source"]["repository"])
            str(image["source"]["tag"])
            str(image["destination"]["repository"])
            try:
                str(image["destination"]["tag"])
            except KeyError:
                logger.debug("no destination tag provided - using source tag as a fallback")
                str(image["source"]["tag"])
    except KeyError:
        logger.critical("syntax error in list file provided")
        exit(1)
    logger.success("input file successfully validated")
    return True


def pull_image(repository: str, tag: str) -> bool:
    """performs a `docker pull`

    Args:
        repository (str): URI of repository
        tag (str): image tag

    Returns:
        bool: success or failure
    """
    try:
        logger.info(f"{repository}:{tag} - pulling image")
        docker_client.images.pull(repository, tag=tag)
        logger.success(f"{repository}:{tag} - image pulled successfully")
        return True
    except docker.errors.APIError or docker.errors.ImageNotFound as e:
        logger.warning(e)
        return False


def push_image(repository: str, tag: str) -> bool:
    """issues with not handling errors correctly:
        https://github.com/docker/docker-py/issues/1772
        https://github.com/docker/docker-py/issues/2226

    Args:
        repository (str): destination repository FQDN
        tag (str): destination tag

    Returns:
        bool: success or failure
    """
    try:
        logger.info(f"{repository}:{tag} - pushing image")
        docker_client.images.push(repository, tag=tag)
        return True
    except docker.errors.APIError as e:
        logger.error(f"{repository}:{tag} - failed to push image")
        return False


def verify_local_image(
    docker_api: str,
    source_endpoint: str,
    source_repository: str,
    source_tag: str,
    destination_repository: str,
    destination_tag: str,
    final_sha256: str,
) -> bool:
    """checks for the image locally, pulls if it isn't, and re-tags it

    Args:
        docker_api (str): API object
        source_endpoint (str): source endpoint to look for (repository+tag)
        source_repository (str): source repository to look for
        source_tag (str): source tag to look for
        destination_repository (str): destination repository for re-tagging
        destination_tag (str): destination tag tag for re-tagging
        final_sha256 (str): sha256 to look for

    Returns:
        bool: success or failure
    """
    try:
        # append sha256 if needed
        if final_sha256 != "":
            source_endpoint_and_sha256: str = str(f"{source_endpoint}@{final_sha256}")
            docker_client.images.list(filters={"reference": f"{source_endpoint_and_sha256}"})
            logger.info(f"{source_endpoint_and_sha256} - source image exists locally")
        else:
            docker_client.images.list(filters={"reference": f"{source_endpoint}"})
            logger.info(f"{source_endpoint} - source image exists locally")

        # replace docker.io as its implicit and not returned by the API when doing lookups
        docker_api.tag(source_endpoint, destination_repository, destination_tag)  # type: ignore
        return True
    except docker.errors.ImageNotFound as e:
        logger.warning(f"{source_endpoint} - image not found locally")
        logger.debug(e)
        pull_image(source_repository, source_tag)
        return False


def verify_destination_image(docker_client: Any, uri: str) -> Tuple[str, int]:
    """verify the image exists in the destination

    Args:
        uri (str): container image:tag

    Returns:
        bool: True if destination image already exists
    """
    try:
        docker_client.images.get_registry_data(uri)
        logger.debug(f"{uri} - verified this exists in destination")
        return "exists", 200
    except docker.errors.ImageNotFound as e:  # reasonable error
        return "does not exist", int(e.status_code)
    except docker.errors.APIError as e:  # bad error
        return f"{e.explanation}", int(e.status_code)


def valid_sha256(sha256_hash: str) -> bool:
    """validates sha256 string

    Args:
        sha256_hash (str): string containing sha256 for image

    Returns:
        bool: True if it is a valid sha256 string
    """
    if re.search(r"\b[A-Fa-f0-9]{64}\b", sha256_hash):  # https://stackoverflow.com/a/43599586/11051914
        return True
    else:
        return False


def check_remote(
    arguments: Any,
    docker_api: Any,
    source_endpoint: str,
    source_repository: str,
    source_tag: str,
    destination_endpoint: str,
    destination_repository: str,
    destination_tag: str,
    final_sha256: str,
    force_pull: bool,
    force_push: bool,
) -> bool:
    """figure out whether to force pull/push, and if not, check destination to see if pushing is required

    Args:
        arguments (Any): cli arguments
        docker_api (Any): api object
        source_endpoint (str): source endpoint to look for (repository+tag)
        source_repository (str): source repository to look for
        source_tag (str): source tag to look for
        destination_endpoint (str): full endpoint URI including tag
        destination_repository (str): destination repository for re-tagging
        destination_tag (str): destination tag tag for re-tagging
        final_sha256 (str): sha256 to look for
        force_pull (bool): force pull, used for immutable tags
        force_push (bool): force push, used for immutable tags
    """
    if arguments.force_pull_push or force_pull:
        pull_image(source_repository, source_tag)
    if arguments.force_pull_push or force_push:
        push_image(destination_repository, destination_tag)
        sleep(1)

    verify_destination, status_code = verify_destination_image(docker_client, destination_endpoint)
    if verify_destination == "exists":
        logger.info(f"{destination_endpoint} - destination image exists in registry")
        # image_already_pushed = True
    elif (verify_destination == "does not exist") or (status_code == 404):
        logging.warning(f"{destination_endpoint} - destination image not found in registry")
        # see if image exists locally and pull from the source registry if it doesn't
        verify_local_image(
            docker_api, source_endpoint, source_repository, source_tag, destination_repository, destination_tag, final_sha256
        )
        push_image(destination_repository, destination_tag)
    else:
        logger.error(f"{destination_endpoint} - {verify_destination}")

    return True


def actions(arguments: Any, docker_api: Any, image_list: Any) -> bool:
    """performs bulk of logic with replicating images

    Args:
        docker_api (Any): client object
        image_list (dict): list of images to parse to perform pull/push
        args (Any): CLI arguments

    Returns:
        bool: True if no show-stopping exceptions
    """
    logger.info(f"preparing threads. Maximum threads: {arguments.max_workers}")
    thread_pool = ThreadPoolExecutor(max_workers=arguments.max_workers)
    for image in list(image_list["images"]):
        # remove docker.io registry prefix as its implicit and not returned by the API when doing lookups
        source_repository: str = re.sub(r"^docker.io/", "", str(image["source"]["repository"]))
        source_tag: str = str(image["source"]["tag"])
        destination_repository: str = str(image["destination"]["repository"])
        destination_tag: str = str()

        # check forcePull and forcePush values
        try:
            force_pull: bool = bool(image["source"]["forcePull"])
        except KeyError:
            force_pull = False
        try:
            force_push: bool = bool(image["source"]["forcePush"])
        except KeyError:
            force_push = False

        # destination tag is optional, falls back to source tag
        try:
            destination_tag = str(image["destination"]["tag"])
        except KeyError:
            logger.debug("no destination tag provided - using source tag as a fallback")
            destination_tag = str(image["source"]["tag"])

        # use []source.sha256 if its valid
        final_sha256: str = ""
        try:
            source_sha256: str = str(image["source"]["sha256"])
            if valid_sha256(source_sha256):
                final_sha256 = source_sha256
                logger.debug(f"{final_sha256} - using this valid sha256")
            else:
                logger.warning(f"{source_repository}:@sha256:{source_sha256} - skipping image because sha256 is not valid")
                break
        except KeyError:
            logger.debug("no valid source sha256 provided, not using sha256 suffix on image URI")

        # combine repositories and tags
        source_endpoint: str = str(f"{source_repository}:{source_tag}")
        destination_endpoint: str = str(f"{destination_repository}:{destination_tag}")

        # create threads
        threads = [
            thread_pool.submit(
                check_remote,
                arguments,
                docker_api,
                source_endpoint,
                source_repository,
                source_tag,
                destination_endpoint,
                destination_repository,
                destination_tag,
                final_sha256,
                force_pull,
                force_push,
            )
        ]

    wait(threads, return_when="ALL_COMPLETED")
    return True


def main(docker_api: Any) -> None:
    """main

    Args:
        docker_client (Any): client object
        docker_api (Any): api object
    """
    arguments = init_arg_parser()

    if arguments.log_level == "INFO":
        log_level = "INFO"
    elif arguments.log_level == "ERROR":
        log_level = "ERROR"
    elif arguments.log_level == "DEBUG":
        log_level = "DEBUG"
    else:
        print("failed to determine the specified value for --log-level")

    if arguments.no_colors:
        logger.basicConfig(
            level=eval(f"logger.{log_level}"),
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            stream=stdout,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    else:
        coloredlogs.install(level=log_level, fmt="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")

    try:
        # image_list: Dict[LiteralString, List[Any]] = yaml.safe_load(Path(arguments.input_file).read_text())
        image_list = yaml.safe_load(Path(arguments.input_file).read_text())
        parse_image_list_yaml(image_list)
        actions(arguments, docker_api, image_list)
    except FileNotFoundError:
        logger.critical(f"input file not found. I cannot continue: {Path(arguments.input_file)}")
    except yaml.parser.ParserError as e:
        logger.critical(f"failed to parse input file: {Path(arguments.input_file)} with error: {e}")


if __name__ == "__main__":
    try:
        docker_client, docker_api = init_docker()
        main(docker_api)
        docker_client.close()
    except KeyboardInterrupt:
        docker_client.close()
        exit(1)
