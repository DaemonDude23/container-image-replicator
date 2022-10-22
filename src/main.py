#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from sys import stdout

import docker
import yaml

# import fnmatch
# import os

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
            prog="container-image-replicator",
            description="container-image-replicator",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        args = parser.add_argument_group()
        args.add_argument("input_file", action="store", help="path to YAML file containing registry information", type=Path)
        args.add_argument("--version", "-v", action="version", version="v0.1.0")

        arguments = parser.parse_args()
        return arguments
    except argparse.ArgumentError:
        exit(1)


# def findReplace(directory, find, replace, filePattern):
#     """
#     https://stackoverflow.com/a/6257321/11051914
#     """
#     for path, _, files in os.walk(os.path.abspath(directory)):
#         for filename in fnmatch.filter(files, filePattern):
#             filepath = os.path.join(path, filename)
#             with open(filepath) as f:
#                 s = f.read()
#             s = s.replace(find, replace)
#             with open(filepath, "w") as f:
#                 f.write(s)


def parse_image_list_yaml(image_list: str) -> bool:
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
        tag (str): _description_

    Returns:
        bool: _description_
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
        bool: _description_
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
        docker_api.tag(source_endpoint, destination_repository, destination_tag)
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
        # docker_client.images.get(uri)
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


def actions(docker_client, docker_api, image_list: list) -> bool:
    """performs bulk of logic with replicating images

    Args:
        image_list (list): list of images to parse to perform pull/push

    Returns:
        bool: True if no show-stopping exceptions
    """
    for image in list(image_list["images"]):
        # remove docker.io registry prefix as its implicit and not returned by the API when doing lookups
        source_repository: str = re.sub(r"^docker.io/", "", str(image["source"]["repository"]))
        source_tag: str = str(image["source"]["tag"])
        destination_repository: str = str(image["destination"]["repository"])

        # destination tag is optional, falls back to source tag
        try:
            destination_tag: str = str(image["destination"]["tag"])
        except KeyError:
            logging.debug("no destination tag provided - using source tag as a fallback")
            destination_tag: str = str(image["source"]["tag"])

        # use []source.sha256 if its valid
        final_sha256: str = ""
        try:
            source_sha256: str = str(image["source"]["sha256"])
            if valid_sha256(source_sha256):
                final_sha256 = source_sha256
                logging.debug(f"{final_sha256} - using this valid sha256")
            else:
                logging.warning(f"{source_repository}:{source_tag}@sha256:{source_sha256} - skipping image because sha256 is not valid")
                break
        except KeyError:
            logging.debug("no valid source sha256 provided, not using sha256 suffix on image URI")

        # combine repositories and tags
        source_endpoint: str = str(f"{source_repository}:{source_tag}")
        destination_endpoint: str = str(f"{destination_repository}:{destination_tag}")

        # see if image exists locally and pull from the source registry if it doesn't
        verify_local_image(
            docker_api, source_endpoint, source_repository, source_tag, destination_repository, destination_tag, final_sha256
        )

        # don't push image if its already in the destination
        if not verify_destination_image(docker_client, destination_endpoint):
            push_image(destination_repository, destination_tag)
            if verify_destination_image(docker_client, destination_endpoint):
                logging.info(f"{destination_endpoint} - image pushed successfully")
            else:
                logging.critical(f"{destination_endpoint} - a silent error occurred when pushing the image")
        else:
            logging.info(f"{destination_endpoint} - already present in destination. Skipping push")

        print("----------------------------------------")
    return True


def main(docker_client, docker_api):
    """main

    Args:
        docker_client (_type_): client object
        docker_api (_type_): api object
    """
    arguments = init_arg_parser()
    image_list: dict = yaml.safe_load(Path(arguments.input_file).read_text())
    parse_image_list_yaml(image_list)
    actions(docker_client, docker_api, image_list)


if __name__ == "__main__":
    try:
        docker_client, docker_api = init_docker()
        main(docker_client, docker_api)
        docker_client.close()
    except KeyboardInterrupt or SystemExit:
        docker_client.close()
        exit(1)
