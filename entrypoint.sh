#!/bin/bash
set -e

echo "========================================"
echo "Secure Voting System - Docker Container"
echo "========================================"

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
while ! nc -z mongodb 27017; do
  sleep 1
done
echo "MongoDB is ready!"

# Execute the main command
exec "$@"
