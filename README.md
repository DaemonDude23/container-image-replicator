**container-image-replicator**

- [About](#about)
- [Usage](#usage)
  - [CLI](#cli)
  - [Config File](#config-file)
- [Configuration](#configuration)
  - [Requirements:](#requirements)
  - [Installation](#installation)
  - [Putting it in your `$PATH`](#putting-it-in-your-path)
    - [Linux (Simplest Option)](#linux-simplest-option)
    - [virtualenv with pip](#virtualenv-with-pip)
  - [Run](#run)
    - [Example](#example)
    - [kubectl to list all of your container images](#kubectl-to-list-all-of-your-container-images)
- [References](#references)
- [Dev](#dev)
  - [`mypy` for type hinting](#mypy-for-type-hinting)
  - [Code Validation](#code-validation)

---

[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Naereen/StrapDown.js/graphs/commit-activity)
![Maintainer](https://img.shields.io/badge/maintainer-DaemonDude23-blue)

[![Linux](https://svgshare.com/i/Zhy.svg)](https://svgshare.com/i/Zhy.svg)
[![Windows](https://svgshare.com/i/ZhY.svg)](https://svgshare.com/i/ZhY.svg)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Package Application with Pyinstaller](https://github.com/DaemonDude23/container-image-replicator/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/DaemonDude23/container-image-replicator/actions/workflows/main.yaml)

# About

It's always a good idea to maintain your own copies of container images you depend on.
Whether there's an outage with an upstream registry provider, [rate limiting](https://docs.docker.com/docker-hub/download-rate-limit/), speed, saving on bandwidth costs with AWS ECR VPC endpoints, it's just a good idea to keep your containers close and within your control.

**container-image-replicator** takes a YAML file that looks something like this:

```yaml
---
images:
  - destination:
      repository: 000000000000.dkr.ecr.us-east-1.amazonaws.com/nginx
      # tag: 1.23.2-alpine  # optional
    source:
      repository: docker.io/nginx
      tag: 1.23.2-alpine
      # sha256: fcba10206c0e29bc2c6c5ede2d64817c113de5bfaecf908b3b7b158a89144162  # optional
  - destination:
      repository: 000000000000.dkr.ecr.us-east-1.amazonaws.com/apache
      tag: 2.4.54  # optional
    source:
      repository: docker.io/httpd
      tag: 2.4.54-alpine
```

And pulls/downloads the image from the source repository, re-tags it, and pushes/uploads it into the destination registry.
You can re-tag an image however you like, or keep it the same as it was.

# Usage

**This script does not handle authentication!**

If you're logging into [AWS ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/getting-started-cli.html), for example, first login with something like:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 000000000000.dkr.ecr.us-east-1.amazonaws.com
```
See [References](#references).

## CLI

```
usage: container-image-replicator [-h] [--max-workers MAX_WORKERS] [--force-pull-push] [--version] input_file

container-image-replicator

options:
  -h, --help            show this help message and exit

optional:
  --max-workers MAX_WORKERS
                        maximum number of worker threads to execute at any one time. One thread per container image (default: 2)
  --force-pull-push     don't check destination or local image cache and pull and push. Useful for mutable tags (default: False)
  --version, -v         show program's version number and exit

required:
  input_file            path to YAML file containing registry information
```

## Config File

This is a description of of the fields available in the config file:
```yaml
---
images:  # required
  - destination:  # required
      repository: 000000000000.dkr.ecr.us-east-1.amazonaws.com/nginx  # required - image repository of destination
      tag: 1.23.2-alpine  # optional - if this isn't populated, the source tag is used for the destination
    source:  # required
      repository: docker.io/nginx  # required
      tag: 1.23.2-alpine  # required - image tag from source repository
      sha256: fcba10206c0e29bc2c6c5ede2d64817c113de5bfaecf908b3b7b158a89144162  # optional
```

# Configuration

## Requirements:

- Python `3.7+` (or manually adjust [./src/requirements.txt](./src/requirements.txt) with more broad constraints)
- `docker` installed and running on the system where this script executed, and sufficient permissions for the user executing `container-image-replicator`

## Installation

- Check the assets for releases for single-file releases of this script with dependencies.
- For local installation/use of the raw script, I use a local virtual environment to isolate dependencies:

```bash
git clone https://github.com/DaemonDude23/container-image-replicator.git -b b0.6.0
cd container-image-replicator
```

## Putting it in your `$PATH`

### Linux (Simplest Option)

1. Create symlink:
```bash
sudo ln -s /absolute/path/to/src/container-image-replicator.py /usr/local/bin/container-image-replicator
```
2. Install dependencies:
```bash
# latest and greatest dependency versions
pip3 install -U -r /path/to/src/requirements.txt
```

### virtualenv with pip

```bash
# assuming virtualenv is already installed...
virtualenv --python=python3.10 ./venv/
source ./venv/bin/activate
./venv/bin/python -m pip install --upgrade pip
pip3 install -U -r ./src/requirements.txt
```

## Run

### Example

```bash
./src/main.py ./tests/yamls/test.yaml
```
```bash
2022-10-22T15:19:24+0000 INFO input file successfully validated
2022-10-22T15:19:24+0000 INFO preparing threads. Maximum threads: 2
2022-10-22T15:19:24+0000 INFO nginx:1.23.2-alpine - source image exists locally
2022-10-22T15:19:29+0000 INFO 000000000000.dkr.ecr.us-east-1.amazonaws.com/nginx:1.23.2-alpine - already present in destination. Skipping push
2022-10-22T15:19:29+0000 INFO httpd:2.4.54-alpine - source image exists locally
2022-10-22T15:19:29+0000 WARNING httpd:2.4.54-alpine - image not found locally
2022-10-22T15:19:29+0000 INFO httpd:2.4.54-alpine - pulling image
2022-10-22T15:19:33+0000 INFO httpd:2.4.54-alpine - image pulled successfully
2022-10-22T15:19:36+0000 INFO 000000000000.dkr.ecr.us-east-1.amazonaws.com/apache:2.4.54 - pushing image
2022-10-22T15:19:45+0000 INFO 000000000000.dkr.ecr.us-east-1.amazonaws.com/apache:2.4.54 - image pushed successfully
```

### kubectl to list all of your container images

```bash
kubectl get pods --all-namespaces \
  -o jsonpath="{.items[*].spec.containers[*].image}" | \
  tr -s '[[:space:]]' '\n' | sort | uniq -c
```

# References

- [AWS ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/getting-started-cli.html)
- [GCP Registry Authentication](https://cloud.google.com/container-registry/docs/advanced-authentication)
- [Azure Container Registry Authentication](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-authentication?tabs=azure-cli)

# Dev

- [docker-py](https://docker-py.readthedocs.io/en/stable/index.html)

## `mypy` for type hinting

```bash
mypy ./src/main.py --check-untyped-defs
```

## Code Validation

```bash
mypy --install-types --non-interactive --ignore-missing-imports src/main.py
```
