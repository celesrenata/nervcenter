#!/bin/bash
set -e

echo "Starting NerveCenter with Docker Compose..."

# Start services
docker-compose -f deployments/local/docker-compose.yaml up -d

echo "Services started! Access the application at http://localhost:8080"