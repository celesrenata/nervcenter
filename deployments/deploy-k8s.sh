# NerveCenter deployment scripts

#!/bin/bash
set -e

echo "Deploying NerveCenter to Kubernetes..."

# Apply Kubernetes manifests
kubectl apply -f deployments/kubernetes/base/

# Check if namespace exists, create if not
kubectl get namespace nervcenter || kubectl create namespace nervcenter

# Apply environment-specific overlay if it exists
if [ -d "deployments/kubernetes/overlays" ]; then
    kubectl kustomize deployments/kubernetes/overlays/production | kubectl apply -f -
fi

echo "Deployment complete!"