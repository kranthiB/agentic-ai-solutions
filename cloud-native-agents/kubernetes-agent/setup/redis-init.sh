#!/bin/bash
# redis-init.sh - Initialize Redis for Agent Core

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until redis-cli -h redis ping | grep -q "PONG"; do
  echo "Redis not ready yet, waiting..."
  sleep 2
done
echo "Redis is ready!"

# Set some configuration values
redis-cli -h redis CONFIG SET maxmemory-policy volatile-lru
redis-cli -h redis CONFIG SET maxmemory "1gb"

# Set up some basic keys (optional)
redis-cli -h redis SET agent_core:init_timestamp "$(date +%s)"
redis-cli -h redis SET agent_core:version "0.1.0"

echo "Redis initialization completed"