# NerveCenter Deployment Documentation

## Overview

This directory contains all deployment configurations for NerveCenter. It includes configurations for Nix, Kubernetes, and local development environments.

## Deployment Options

### Nix Deployment

For local development, use the Nix deployment configuration:

```bash
nix-shell deployments/nix/devShell.nix
```

### Kubernetes Deployment

To deploy to Kubernetes, use the following command:

```bash
./deployments/deploy-k8s.sh
```

### Local Deployment

For local development with Docker Compose:

```bash
./deployments/deploy-local.sh
```

## Environment Configuration

Environment-specific configurations are available in:

- `.env.development` - Development environment
- `.env.staging` - Staging environment
- `.env.production` - Production environment

## Directory Structure

```
/deployments
  ├── nix/
  │   ├── default.nix
  │   └── devShell.nix
  ├── kubernetes/
  │   ├── base/
  │   │   ├── deployment.yaml
  │   │   ├── service.yaml
  │   │   ├── configmap.yaml
  │   │   └── secret.yaml
  │   └── kustomization.yaml
  ├── local/
  │   ├── docker-compose.yaml
  │   └── Dockerfile
  ├── .env.development
  ├── .env.staging
  ├── .env.production
  ├── deploy-k8s.sh
  ├── deploy-local.sh
  └── deploy-nix.sh
```

## Getting Started

1. Choose your deployment target (Nix, Kubernetes, or local)
2. Follow the specific deployment instructions
3. Configure your environment variables
4. Start the application

## Troubleshooting

For common issues and solutions, refer to the [Troubleshooting Guide](TROUBLESHOOTING.md).