import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from sys import exit
from typing import Any
from typing import Dict
from typing import Tuple

import docker
from typing_extensions import LiteralString

from push import push_image


def parse_image_list_replicate(logger: Any, image: Dict[LiteralString, Any]) -> None:
    try:
        isinstance(image["source"]["repository"], str)
        isinstance(image["source"]["tag"], str)
        try:
            isinstance(image["destination"]["tag"], str | int | float)
        except KeyError:
            logger.debug("no destination tag provided - using source tag as a fallback")
    except KeyError as e:
        logger.critical(f"syntax error in list file provided: {e}")
        exit(1)


def check_remote(
    logger: Any,
    arguments: Any,
    docker_api: Any,
    docker_client: Any,
    source_endpoint: LiteralString,
    source_repository: LiteralString,
    source_tag: LiteralString,
    destination_endpoint: LiteralString,
    destination_repository: LiteralString,
    destination_tag: LiteralString,
    final_sha256: LiteralString,
    force_pull: bool,
    force_push: bool,
) -> bool:
    """figure out whether to force pull/push, and if not, check destination to see if pushing is required

    Args:
        arguments (Any): cli arguments
        docker_api (Any): api object
        source_endpoint (LiteralString): source endpoint to look for (repository+tag)
        source_repository (LiteralString): source repository to look for
        source_tag (LiteralString): source tag to look for
        destination_endpoint (LiteralString): full endpoint URI including tag
        destination_repository (LiteralString): destination repository for re-tagging
        destination_tag (LiteralString): destination tag tag for re-tagging
        final_sha256 (LiteralString): sha256 to look for
        force_pull (bool): force pull, used for immutable tags
        force_push (bool): force push, used for immutable tags
    """
    if arguments.force_pull_push or force_pull:
        pull_image(logger, docker_client, source_repository, source_tag)
    if arguments.force_pull_push or force_push:
        push_image(logger, docker_client, destination_repository, destination_tag)

    verify_destination, status_code = verify_destination_image(logger, docker_client, destination_endpoint)
    if verify_destination == "exists":
        logger.info(f"{destination_endpoint} - destination image exists in registry")
    elif verify_destination == "does not exist" or status_code == 404:
        logger.warning(f"{destination_endpoint} - destination image not found in registry")
        # see if image exists locally and pull from the source registry if it doesn't
        verify_local_image(
            logger,
            docker_api,
            docker_client,
            source_endpoint,
            source_repository,
            source_tag,
            destination_repository,
            destination_tag,
            final_sha256,
        )
        push_image(logger, docker_client, destination_repository, destination_tag)
    else:
        logger.error(f"{destination_endpoint} - {verify_destination}")

    return True


def verify_local_image(
    logger: Any,
    docker_api: Any,
    docker_client: Any,
    source_endpoint: LiteralString,
    source_repository: LiteralString,
    source_tag: LiteralString,
    destination_repository: LiteralString,
    destination_tag: LiteralString,
    final_sha256: LiteralString,
) -> bool:
    """checks for the image locally, pulls if it isn't, and re-tags it

    Args:
        docker_api (Any): API object
        source_endpoint (LiteralString): source endpoint to look for (repository+tag)
        source_repository (LiteralString): source repository to look for
        source_tag (LiteralString): source tag to look for
        destination_repository (LiteralString): destination repository for re-tagging
        destination_tag (LiteralString): destination tag tag for re-tagging
        final_sha256 (LiteralString): sha256 to look for

    Returns:
        bool: True if local image tag is found
    """
    matched_images = list()
    try:  # append sha256 if needed
        if final_sha256 != "":
            source_endpoint_and_sha256: str = str(f"{source_endpoint}@{final_sha256}")
            matched_images = docker_client.images.list(filters={"reference": f"{source_endpoint_and_sha256}"})
            if len(matched_images) > 0:
                logger.info(f"{source_endpoint_and_sha256} - source image exists locally")
            else:
                logger.warning(f"{source_endpoint_and_sha256} - image not found locally")
                pull_image(logger, docker_client, source_repository, source_tag)
                return False
        else:  # no sha256, just a tag
            matched_images = docker_client.images.list(filters={"reference": f"{source_endpoint}"})
            if len(matched_images) > 0:
                logger.info(f"{source_endpoint} - source image exists locally")
            else:
                logger.warning(f"{source_endpoint} - image not found locally")
                pull_image(logger, docker_client, source_repository, source_tag)
                matched_images = docker_client.images.list(filters={"reference": f"{source_endpoint}"})

        # tag it
        matched_images[0].tag(repository=destination_repository, tag=destination_tag)
        return True
    except docker.errors.ImageNotFound as e:
        logger.warning(f"{source_endpoint} - image not found locally")
        logger.debug(e)
        pull_image(logger, docker_client, source_repository, source_tag)
        return False


def pull_image(logger: Any, docker_client: Any, repository: LiteralString, tag: LiteralString) -> bool:
    """performs a `docker pull`

    Args:
        repository (LiteralString): URI of repository
        tag (LiteralString): image tag

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


def replicate(logger: Any, arguments: Any, docker_api: Any, docker_client: Any, image_list: list[dict[str, Any]]) -> bool:
    """performs bulk of logic with replicating images from one place to another

    Args:
        arguments (Any): CLI arguments
        docker_api (Any): client object
        image_list (Dict[LiteralString, Any]): list of images to parse to perform pull/push

    Returns:
        bool: _description_
    """
    logger.info(f"preparing threads for replicating. Maximum threads: {arguments.max_workers}")
    thread_pool = ThreadPoolExecutor(max_workers=arguments.max_workers)
    for image in list(image_list):
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

        # use images.[]source.sha256 if its valid
        final_sha256: str = ""
        try:
            source_sha256: str = str(image["source"]["sha256"])
            if validate_sha256(source_sha256):
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
                logger,
                arguments,
                docker_api,
                docker_client,
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


def validate_sha256(sha256_hash: LiteralString) -> bool:
    """validates sha256 string

    Args:
        sha256_hash (LiteralString): string containing sha256 for image

    Returns:
        bool: True if it is a valid sha256 string
    """
    if re.search(r"\b[A-Fa-f0-9]{64}\b", sha256_hash):  # https://stackoverflow.com/a/43599586/11051914
        return True
    else:
        return False


def verify_destination_image(logger: Any, docker_client: Any, uri: LiteralString) -> Tuple[str, int]:
    """verify the image exists in the destination

    Args:
        docker_client (Any): docker client object
        uri (LiteralString): container image:tag

    Returns:
        Tuple[str, int]: status in the form of text (potentially including error), and error code
    """
    try:
        docker_client.images.get_registry_data(uri)
        logger.debug(f"{uri} - verified this exists in destination")
        return "exists", 200
    except docker.errors.ImageNotFound as e:  # reasonable error
        return "does not exist", int(e.status_code)
    except docker.errors.APIError as e:  # bad error
        return f"{e.explanation}", int(e.status_code)
