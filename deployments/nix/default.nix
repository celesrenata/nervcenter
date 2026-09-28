# Nix deployment configuration for NerveCenter local development

{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python3
    pkgs.nodejs
    pkgs.postgresql
    pkgs.redis
  ];

  shellHook = ""
    # Set up environment variables
    export DATABASE_URL=postgresql://localhost/nervcenter
    export REDIS_URL=redis://localhost
    export PYTHONPATH=${PYTHONPATH}:./backend
    export NODE_PATH=${NODE_PATH}:./web
  "";

  # Add any additional configuration or scripts here
}