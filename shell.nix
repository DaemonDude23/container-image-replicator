{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixpkgs-unstable.tar.gz") {} }:

pkgs.mkShell rec {
  buildInputs = [
    pkgs.python313
    pkgs.git
  ];

  # Use a local venv and install pinned pip deps from requirements.txt.
  venvDir = "venv";

  shellHook = ''
    set -e
    export VENV_PATH="$PWD/${venvDir}"
    export VIRTUAL_ENV="$VENV_PATH"
    export PATH="$VENV_PATH/bin:$PATH"
    export PYTHONNOUSERSITE=1

    # Create venv if missing (we manage it ourselves to keep VSCode happy).
    if [ ! -d "$VENV_PATH" ]; then
      python -m venv "$VENV_PATH"
    fi

    # Install/refresh requirements when the hash changes.
    REQ_FILE="$PWD/src/requirements.txt"
    REQ_HASH=$(sha256sum "$REQ_FILE" | cut -d' ' -f1)
    HASH_FILE="$VENV_PATH/.requirements-installed"
    if [ ! -f "$HASH_FILE" ] || [ "$REQ_HASH" != "$(cat "$HASH_FILE")" ]; then
      "$VENV_PATH/bin/pip" install --upgrade pip
      "$VENV_PATH/bin/pip" install -r "$REQ_FILE"
      echo "$REQ_HASH" > "$HASH_FILE"
    fi

    source "$VENV_PATH/bin/activate"
    echo "Setting up the environment..."
    sed -i 's/\r$//' ./src/*.py
  '';
}
