#!/bin/bash
# qdrant-init.sh - Initialize Qdrant collections for Agent Core

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
until curl -s -f "http://qdrant:6333/readiness" > /dev/null; do
  echo "Qdrant not ready yet, waiting..."
  sleep 2
done
echo "Qdrant is ready!"

# Create knowledge_vectors collection
echo "Creating knowledge_vectors collection..."
curl -X PUT "http://qdrant:6333/collections/kubernetes_knowledge" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    },
    "optimizers_config": {
      "default_segment_number": 2
    },
    "replication_factor": 1,
    "write_consistency_factor": 1
  }'

# Create conversation_vectors collection
echo "Creating conversation_vectors collection..."
curl -X PUT "http://qdrant:6333/collections/conversation_history" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    },
    "optimizers_config": {
      "default_segment_number": 2
    },
    "replication_factor": 1,
    "write_consistency_factor": 1
  }'

# Create documentation_vectors collection
echo "Creating documentation_vectors collection..."
curl -X PUT "http://qdrant:6333/collections/documentation_vectors" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    },
    "optimizers_config": {
      "default_segment_number": 2
    },
    "replication_factor": 1,
    "write_consistency_factor": 1
  }'

echo "Qdrant initialization completed"