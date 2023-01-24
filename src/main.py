#!/usr/bin/env python3
import argparse
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from pathlib import Path
from sys import stdout

# noreorder
import docker, yaml  # type: ignore
import yaml  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)


def init_docker():
    docker_client = docker.from_env()
    docker_api = docker.APIClient()
    return docker_client, docker_api


def init_arg_parser():
    try:
        parser = argparse.ArgumentParser(
            description="description: make copies of container images from one registry to another",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="container-image-replicator",
        )
        args_optional = parser.add_argument_group("optional")
        args_required = parser.add_argument_group("required")
        args_optional.add_argument(
            "--max-workers",
            action="store",
            default=2,
            dest="max_workers",
            help="maximum number of worker threads to execute at any one time. One thread per container image",
            type=int,
        )
        args_optional.add_argument(
            "--force-pull-push",
            action="store_true",
            default=False,
            dest="force_pull_push",
            help="don't check destination or local image cache and pull and push.\
                Useful for mutable tags. Be careful, as this can hit rate limits quickly!",
        )
        args_optional.add_argument("--version", "-v", action="version", version="v0.5.0")
        args_required.add_argument("input_file", action="store", help="path to YAML file containing registry information", type=Path)

        arguments = parser.parse_args()
        return arguments
    except argparse.ArgumentError:
        logging.fatal("failed to parse arguments")
        exit(1)


def parse_image_list_yaml(image_list: dict) -> bool:
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
                logging.debug("no destination tag provided - using source tag as a fallback")
                str(image["source"]["tag"])
    except KeyError:
        logging.fatal("syntax error in list file provided")
        exit(1)
    logging.info("input file successfully validated")
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
        logging.info(f"{repository}:{tag} - pulling image")
        docker_client.images.pull(repository, tag=tag)
        logging.info(f"{repository}:{tag} - image pulled successfully")
        return True
    except docker.errors.APIError or docker.errors.ImageNotFound as e:
        logging.warning(e)
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
        logging.info(f"{repository}:{tag} - pushing image")
        docker_client.images.push(repository, tag=tag)
        return True
    except docker.errors.APIError as e:
        logging.critical(f"{repository}:{tag} - failed to push image")
        logging.critical(e)
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
            logging.info(f"{source_endpoint_and_sha256} - source image exists locally")
        else:
            docker_client.images.list(filters={"reference": f"{source_endpoint}"})
            logging.info(f"{source_endpoint} - source image exists locally")

        # replace docker.io as its implicit and not returned by the API when doing lookups
        docker_api.tag(source_endpoint, destination_repository, destination_tag)  # type: ignore
        return True
    except docker.errors.ImageNotFound as e:
        logging.warning(f"{source_endpoint} - image not found locally")
        logging.debug(e)
        pull_image(source_repository, source_tag)
        return False


def verify_destination_image(docker_client, uri: str) -> bool:
    """verify the image exists in the destination

    Args:
        uri (str): container image:tag

    Returns:
        bool: True if destination image already exists
    """
    try:
        docker_client.images.get_registry_data(uri)
        logging.debug(f"{uri} - verified exists in destination")
        return True
    except docker.errors.APIError or docker.errors.ImageNotFound as e:
        logging.debug(e)
        return False


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
    arguments,
    docker_api,
    source_endpoint: str,
    source_repository: str,
    source_tag: str,
    destination_endpoint: str,
    destination_repository: str,
    destination_tag: str,
    final_sha256: str,
    force_pull: bool,
    force_push: bool,
):
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
    if arguments.force_pull_push or force_pull or force_push:
        if force_pull:
            pull_image(source_repository, source_tag)
        if force_push:
            push_image(destination_repository, destination_tag)

        if verify_destination_image(docker_client, destination_endpoint):
            logging.info(f"{destination_endpoint} - image pushed successfully")
        else:
            logging.critical(f"{destination_endpoint} - a silent error occurred when pushing the image")
    else:
        if not verify_destination_image(docker_client, destination_endpoint):
            # see if image exists locally and pull from the source registry if it doesn't
            verify_local_image(
                docker_api, source_endpoint, source_repository, source_tag, destination_repository, destination_tag, final_sha256
            )
            push_image(destination_repository, destination_tag)

            if verify_destination_image(docker_client, destination_endpoint):
                logging.info(f"{destination_endpoint} - image pushed successfully")
            else:
                logging.critical(f"{destination_endpoint} - a silent error occurred when pushing the image")
        else:
            logging.info(f"{destination_endpoint} - already present in destination. Skipping push")
    return True


def actions(arguments, docker_api, image_list: dict) -> bool:
    """performs bulk of logic with replicating images

    Args:
        docker_api (Any): client object
        image_list (list): list of images to parse to perform pull/push
        args (Any): CLI arguments

    Returns:
        bool: True if no show-stopping exceptions
    """
    logging.info(f"preparing threads. Maximum threads: {arguments.max_workers}")
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
            logging.debug("no destination tag provided - using source tag as a fallback")
            destination_tag = str(image["source"]["tag"])

        # use []source.sha256 if its valid
        final_sha256: str = ""
        try:
            source_sha256: str = str(image["source"]["sha256"])
            if valid_sha256(source_sha256):
                final_sha256 = source_sha256
                logging.debug(f"{final_sha256} - using this valid sha256")
            else:
                logging.warning(f"{source_repository}:@sha256:{source_sha256} - skipping image because sha256 is not valid")
                break
        except KeyError:
            logging.debug("no valid source sha256 provided, not using sha256 suffix on image URI")

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


def main(docker_api):
    """main

    Args:
        docker_client (Any): client object
        docker_api (Any): api object
    """
    arguments = init_arg_parser()
    image_list = yaml.safe_load(Path(arguments.input_file).read_text())
    parse_image_list_yaml(image_list)
    actions(arguments, docker_api, image_list)


if __name__ == "__main__":
    try:
        docker_client, docker_api = init_docker()
        main(docker_api)
        docker_client.close()
    except KeyboardInterrupt:
        docker_client.close()
        exit(1)
