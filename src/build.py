import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from json import dumps
from pathlib import Path
from sys import exit
from typing import Any
from typing import Dict
from typing import List
from typing import LiteralString
from typing import Optional

from mypy_extensions import KwArg
from mypy_extensions import VarArg


def construct_build(logger: Any, arguments: Any, docker_api: Any, image_list: list[dict[str, Any]]) -> bool:
    logger.info(f"preparing threads for building. Maximum threads: {arguments.max_workers}")
    thread_pool = ThreadPoolExecutor(max_workers=arguments.max_workers)
    for image in list(image_list):
        buildfolder: str = str(image["build"]["build_folder"])
        destination_repository: str = str(image["destination"]["repository"])
        dockerfile: Path = Path(image["build"]["dockerfile"])

        # construct dict to contain build info for this image
        build_args = list(image["build"]["build_args"])
        tags = list(image["build"]["tags"])

        # validations
        # validate dockerfile path
        if Path.is_file(dockerfile):
            logger.debug(f'Dockerfile found at: "{dockerfile}"')
        else:
            logging.error(f"Unable to locate the Dockerfile: \"{image['build']['dockerfile']}\" in {dumps(image)}")
            break  # skip building/pushing

        # TODO validate that there is at least one tag
        # combine repositories and tags
        destination_endpoints = list()
        for tag in tags:
            destination_endpoints.append(f"{destination_repository}:{tag}")

        # create threads
        threads = [thread_pool.submit(docker_build(logger, arguments, docker_api, dockerfile, destination_endpoints, tags, build_args))]

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
    docker_api: Any,
    dockerfile: Path,
    destination_endpoints: List[LiteralString],
    tags: List[LiteralString],
    build_args: List[Dict[str, str | int | float]],
) -> Callable[[VarArg(), KwArg()], Any]:
    logger.success("MOCK successful build and push")
    return "WOO"


def parse_image_list_build(logger: Any, image: Dict[LiteralString, Any]) -> None:
    try:
        isinstance(image["build"], dict)
        # TODO more here
    except KeyError as e:
        logger.critical(f"syntax error in list file provided: {e}")
        exit(1)
