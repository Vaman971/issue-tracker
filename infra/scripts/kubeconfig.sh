#!/usr/bin/env bash
# kubeconfig.sh — configure kubectl to point at the EKS cluster
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
CLUSTER_NAME="${CLUSTER_NAME:-issue-tracker-production}"

echo "Updating kubeconfig for cluster: ${CLUSTER_NAME} (${AWS_REGION})"
aws eks update-kubeconfig \
  --region "${AWS_REGION}" \
  --name "${CLUSTER_NAME}" \
  --alias "${CLUSTER_NAME}"

echo "Current context: $(kubectl config current-context)"
echo "Nodes:"
kubectl get nodes
