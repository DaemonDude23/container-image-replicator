{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixpkgs-unstable.tar.gz") {} }:

pkgs.mkShell {
  buildInputs = [
    (pkgs.python313.withPackages (ps: with ps; [
      coloredlogs
      docker
      mypy-extensions
      pyyaml
      requests
      typing-extensions
      verboselogs
    ]))

    pkgs.git
  ];

  src = ./src;

  shellHook = ''
    echo "Setting up the environment..."
    sed -i 's/\r$//' ./src/*.py
    alias container-image-replicator='python3 $(pwd)/src/container-image-replicator.py'
  '';
}

