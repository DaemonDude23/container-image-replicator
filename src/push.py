from typing import Any

import docker
from typing_extensions import LiteralString


def push_image(logger: Any, docker_client: Any, repository: LiteralString, tag: LiteralString) -> bool:
    """_summary_

    Args:
        repository (LiteralString): destination repository FQDN
        tag (LiteralString): destination tag

    Returns:
        bool: success or failure
    """
    try:
        logger.info(f"{repository}:{tag} - pushing image")
        docker_client.images.push(repository, tag=tag)
        logger.success(f"{repository}:{tag} - imaged pushed successfully")
        return True
    except docker.errors.APIError as e:
        logger.error(f"{repository}:{tag} - failed to push image")
        return False
