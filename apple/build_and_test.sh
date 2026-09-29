#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building NerveCenter..."
swift build

echo "Running tests..."
swift test

echo "Build and test completed successfully!"
