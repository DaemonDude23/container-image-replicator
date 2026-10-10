from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any

import docker

from push import push_image


def construct_build(logger: Any, arguments: Any, docker_client: Any, image_list: list[dict[str, Any]]) -> bool:
    logger.info(f"preparing threads for building. Maximum threads: {arguments.max_workers}")
    futures = []
    with ThreadPoolExecutor(max_workers=arguments.max_workers) as thread_pool:
        for image in image_list:
            build_folder = Path(image["build"]["build_folder"]).resolve()
            dockerfile = Path(image["build"].get("dockerfile", build_folder / "Dockerfile")).resolve()
            destination_repository = str(image["destination"]["repository"])
            build_args = dict(image["build"].get("build_args", {}))
            tags = [str(tag) for tag in image["build"].get("tags", [])]

            if not build_folder.is_dir():
                logger.error(f'Unable to locate the build path: "{build_folder}"')
                continue
            if not dockerfile.is_file():
                logger.error(f'Unable to locate the Dockerfile: "{dockerfile}"')
                continue
            try:
                dockerfile_arg = str(dockerfile.relative_to(build_folder))
            except ValueError:
                logger.error(f'Dockerfile must be inside the build context: "{dockerfile}"')
                continue
            if not tags:
                logger.error(f'No build tags were configured for "{destination_repository}"')
                continue

            futures.append(
                thread_pool.submit(
                    docker_build,
                    logger,
                    docker_client,
                    build_folder,
                    dockerfile_arg,
                    destination_repository,
                    tags,
                    build_args,
                )
            )

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"build worker failed: {e}")
    return True


def docker_build(
    logger: Any,
    docker_client: Any,
    build_folder: Path,
    dockerfile: str,
    repository: str,
    tags: list[str],
    build_args: dict[str, str | int | float],
) -> bool:
    first_tag, *additional_tags = tags
    first_endpoint = f"{repository}:{first_tag}"
    try:
        image, _ = docker_client.images.build(
            path=str(build_folder),
            dockerfile=dockerfile,
            tag=first_endpoint,
            buildargs=build_args,
        )
        logger.success(f"build succeeded: {first_endpoint}")

        for tag in additional_tags:
            endpoint = f"{repository}:{tag}"
            if not image.tag(repository=repository, tag=tag):
                logger.error(f"failed to tag built image: {endpoint}")
                return False

        for tag in tags:
            if not push_image(logger, docker_client, repository, tag):
                return False
            logger.success(f"push (from build) succeeded: {repository}:{tag}")
    except (docker.errors.APIError, docker.errors.BuildError, TypeError) as e:
        logger.error(f"build failed for {repository}: {e}")
        return False

    return True


def parse_image_list_build(logger: Any, image: dict[str, Any]) -> None:
    try:
        if not isinstance(image["build"], dict):
            raise ValueError("build must be a mapping")
        if not isinstance(image["destination"], dict) or not isinstance(image["destination"].get("repository"), str):
            raise ValueError("destination.repository must be a string")
        if not isinstance(image["build"].get("build_folder"), str):
            raise ValueError("build.build_folder must be a string")
        if "dockerfile" in image["build"] and not isinstance(image["build"]["dockerfile"], str):
            raise ValueError("build.dockerfile must be a string")
        if "build_args" in image["build"] and not isinstance(image["build"]["build_args"], dict):
            raise ValueError("build.build_args must be a mapping")
        if not isinstance(image["build"].get("tags"), list) or not image["build"]["tags"]:
            raise ValueError("build.tags must be a non-empty list")
    except (KeyError, TypeError, ValueError) as e:
        logger.critical(f"syntax error in list file provided: {e}")
        raise SystemExit(1)
