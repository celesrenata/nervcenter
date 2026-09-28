#!/bin/bash
set -e

echo "Setting up Nix development environment..."

# Enter the Nix shell
nix-shell deployments/nix/devShell.nix

echo "Nix environment setup complete!"