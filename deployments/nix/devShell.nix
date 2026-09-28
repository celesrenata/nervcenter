# Nix development shell for NerveCenter

{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "nervcenter-dev";

  buildInputs = with pkgs; [
    python3
    python3.pkgs.pip
    python3.pkgs.poetry
    nodejs
    postgresql
    redis
    black
    flake8
    pytest
  ];

  shellHook = ''
    echo "Welcome to NerveCenter development shell"

    # Set up environment variables
    export DATABASE_URL=postgresql://localhost/nervcenter
    export REDIS_URL=redis://localhost
    export PYTHONPATH=${PYTHONPATH}:./backend
    export NODE_PATH=${NODE_PATH}:./web

    # Create necessary directories
    mkdir -p ./data

    echo "Ready to develop NerveCenter!"
  '';
}