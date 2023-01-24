**Changelog**

- [Changelog](#changelog)

---

# [v0.5.0](https://github.com/DaemonDude23/container-image-replicator/releases/tag/v0.5.0) - Jan 23 2023

**Enhancements**

- Add CLI flag `--force-pull-push` to force pulling/pushing images even if the tag exists in the remote repository. Use `[]source.forcePull` and or `[]source.forcePush` to fine-tune these properties on a per-image basis instead of globally with this CLI flag.
  - **Beware as this can count against rate limits. Use wisely!**

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
