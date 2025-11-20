**Changelog - Container Image Replicator**

---

# [v0.12.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.12.0) - November 20 2025

**Bugfixes**

TODO

# [v0.11.1](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.11.1) - October 22 2023

**Bugfixes**

- Fixed issue where CIR was unable to re-tag images.

# [v0.11.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.11.0) - October 22 2023

- No code changes, but now all binaries (Linux. MacOS, Windows) are now a part of this release. Otherwise, just GitHub workflow tweaks.

# [v0.10.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.10.0) - October 3 2023

**Enhancements**

- Added the ability to **build** _and_ push images, not just replicate them from somewhere to somewhere. See config syntax examples in [README.md](README.md).
- Switched to **Nuitka**, replacing **PyInstaller** for generating binaries. Let me know if any of the builds (Linux/Windows/MacOS) have issues.
  - Currently building a Python `3.11.6` image.

**Bugfixes**

- Fixed inconsistent and contradictory reporting from logs about an image being present already, and notify user when an image is pushed successfully.
- Fixed error that prevented the use of the `--no-colors` flag.
  - Added a singular alias for the plural. These have the same effect:
    - `--no-colors`
    - `--no-color`

**Housekeeping**

- pre-commit
  - config updates and enabled `mypy`.
- Corrected some docstrings.
- Added more typing. Bumped minimum Python version to `3.11` due to use of the newer typing mechanisms.
- `PyYAML` package updated.
- Split [`requirements.txt`](src/requirements.txt) into the latest and greatest, or use [`requirements-mac.txt`](src/requirements-mac.txt) if you have a [bug](https://github.com/docker/docker-py/issues/3113) with the `requests` library.

# [v0.9.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.9.0) - June 3 2023

- No code changes, just fixes for the PyInstaller spec files which should fully resolve their issues.

# [v0.8.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.8.0) - June 1 2023

**Enhancements**

- Logging
  - Added support for `success` logs with the `verboselogs` library.
  - Added exception catching for _input file not found_ and _failed to parse scenarios_.
- Added example RegEx named capture group example for those using log aggregation tools.

**Bugfixes**

- Fixed issue where if the destination image didn't already exist, CIR wouldn't attempt a _push_.
- _Hopefully_ fixed the broken PyInstaller binaries.

**Housekeeping**

- pre-commit
  - Removed `mypy` pre-commit hook.
  - Added [`vermin`](https://github.com/netromdk/vermin) to test minimum Python version required, which is `v3.11`
- Docs
  - Added image of prettily-colored screenshot of command output.
- Added TODO list/musings for future plans to expand functionality of this script at the bottom of [README.md](README.md).

# [v0.7.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.7.0) - May 24 2023

**Enhancements**

- Logging
  - Added default coloration of logs (turn it off with argument `--no-colors`).
    - Add much improved error detail instead of `a silent error has occurred`, replacing it with (example) `denied: Your authorization token has expired. Reauthenticate and try again.`

**Bugfixes**

- Update PIP dependencies.
  - Pin `requests` to `<=2.29.0` possibly prevent this issue: [https://github.com/docker/docker-py/issues/3113](https://github.com/docker/docker-py/issues/3113)

**Housekeeping**

- pre-commit-config updates.
  - `mypy --strict` added and more typing.

# [v0.6.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.6.0) - Jan 23 2023

**Enhancements**

- Reduce `if` conditions for force pull or push.
- Remove a redundant check on the destination repo.

# [0.6.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/b0.6.0) - Jan 23 2023

**Enhancements**

- Add CLI flag `--force-pull-push` to force pulling/pushing images even if the tag exists in the remote repository. Use `[]source.forcePull` and or `[]source.forcePush` to fine-tune these properties on a per-image basis instead of globally with this CLI flag.
  - **Beware as this can count against rate limits. Use wisely!**
  - This is useful for when you source images with mutable tags, like `docker.io/httpd:2.4` where the patch version is being updated for this same image tag across time.

**Housekeeping**

- `types-PyYAML` package updated.
- Added to and updated docs.

# [v0.4.2](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.4.2) - Jan 9 2023

**Bugfixes**

- Make `max-workers` actually use that number of threads.

# [v0.4.1](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.4.1) - Dec 27 2022

**Bugfixes**

- Fix exception thrown when using `--version` or `--help`.

# [v0.4.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.4.0) - Dec 27 2022

**Enhancements**

- Added multithreading (with a customizable worker thread count with `--max-workers`. Default = `2`) so that multiple pull/push operations occur in parallel instead of serially as with the previous behavior. Much faster!
- Only pull a source image if the image does not exist in the destination. Previously the image would be downloaded before checking if a push was required at all.

**Bugfixes**

- Present the input file as a **required** argument in `--help`.

**Housekeeping**

- pre-commit-config updates.

# [v0.3.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.3.0) - Nov 13 2022

**Enhancements**

- Updated docker library to `6.0.1`.

**Housekeeping**

- pre-commit-config updates.
