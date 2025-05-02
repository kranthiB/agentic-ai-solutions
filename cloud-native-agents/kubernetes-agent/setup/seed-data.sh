#!/bin/bash
# seed-data.sh - Seed Qdrant with initial knowledge documents

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
until curl -s -f "http://qdrant:6333/collections/kubernetes_knowledge" > /dev/null; do
  echo "Qdrant collections not ready yet, waiting..."
  sleep 2
done
echo "Qdrant collections are ready!"

# Add some basic Kubernetes knowledge points
echo "Seeding knowledge base with basic Kubernetes concepts..."

# Sample document about Pods
curl -X PUT "http://qdrant:6333/collections/kubernetes_knowledge/points" \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [0.01, 0.02, 0.03, ...],
        "payload": {
          "title": "Kubernetes Pod Basics",
          "content": "A Pod is the smallest deployable unit in Kubernetes. It represents a single instance of a running process in your cluster. Pods contain one or more containers, storage resources, a unique network IP, and options that govern how the container(s) should run.",
          "type": "concept",
          "tags": ["kubernetes", "pod", "basics"]
        }
      }
    ]
  }'

echo "Data seeding completed."