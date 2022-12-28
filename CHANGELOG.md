**Changelog**

- [Changelog](#changelog)

---

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
