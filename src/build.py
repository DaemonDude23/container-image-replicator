import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from json import dumps
from pathlib import Path
from sys import exit
from typing import Any
from typing import Dict
from typing import List

import docker
from typing_extensions import LiteralString

from push import push_image


def construct_build(logger: Any, arguments: Any, docker_client: Any, image_list: list[dict[str, Any]]) -> bool:
    logger.info(f"preparing threads for building. Maximum threads: {arguments.max_workers}")
    thread_pool = ThreadPoolExecutor(max_workers=arguments.max_workers)
    for image in list(image_list):
        build_folder: Path = Path(image["build"]["build_folder"])
        destination_repository: str = str(image["destination"]["repository"])
        dockerfile: Path = Path(image["build"]["dockerfile"])

        # construct dict to contain build info for this image
        build_args = dict(image["build"]["build_args"])
        tags = list(image["build"]["tags"])

        # validations
        # validate build_path
        if Path.is_dir(build_folder):
            logger.debug(f'Build path found at: "{build_folder}"')
        else:
            logging.error(f'Unable to locate the build path: "{build_folder}" in {dumps(image)}')
            break  # skip building/pushing

        # validate dockerfile path
        # TODO check if Dockerfile is in the build_folder
        if Path.is_file(dockerfile):
            logger.debug(f'Dockerfile found at: "{dockerfile}"')
        else:
            logging.error(f'Unable to locate the Dockerfile: "{dockerfile}" in {dumps(image)}"')
            break  # skip building/pushing

        # TODO validate that there is at least one tag
        # combine repositories and tags
        destination_endpoints = list()
        for tag in tags:
            destination_endpoints.append(f"{destination_repository}:{tag}")

        # create threads
        threads = [
            thread_pool.submit(
                docker_build, logger, arguments, build_folder, docker_client, dockerfile, destination_endpoints, tags, build_args
            )
        ]

    # if there were no threads just continue
    try:
        if len(threads) > 0:
            wait(threads, return_when="ALL_COMPLETED")
    except UnboundLocalError:
        pass

    return True


def docker_build(
    logger: Any,
    arguments: Any,
    build_folder: Path,
    docker_client: Any,
    dockerfile: Path,
    destination_endpoints: List[LiteralString],
    tags: List[LiteralString],
    build_args: Dict[str, str | int | float],
) -> Any:
    try:
        for endpoint in destination_endpoints:
            repository, tag = endpoint.split(":")

            build = docker_client.images.build(path=str(build_folder), tag=endpoint)
            logger.success(f"build succeeded: {endpoint}")

            push_image(logger, docker_client, repository, tag)
            logger.success(f"push (from build) succeeded: {endpoint}")

    except docker.errors.APIError as e:
        return f"{e}"
    except docker.errors.BuildError as e:
        return f"{e}"
    except TypeError as e:
        return f"{e}"

    return "WOO"


def parse_image_list_build(logger: Any, image: Dict[LiteralString, Any]) -> None:
    try:
        isinstance(image["build"], dict)
        # TODO more here
    except KeyError as e:
        logger.critical(f"syntax error in list file provided: {e}")
        exit(1)
