#!/bin/bash
# Cleanup script for Phixr environment
# Removes Docker containers, images, networks, and volumes related to Phixr

set -e

echo "🧹 Phixr Environment Cleanup"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Check if running in project directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found. Run from project root."
    exit 1
fi

# Stop and remove docker-compose services
print_status "Stopping Docker Compose services..."
docker compose down --volumes --remove-orphans 2>/dev/null || true

# Remove Phixr-related containers
print_status "Removing Phixr containers..."
docker rm -f $(docker ps -a --filter "name=phixr" -q) 2>/dev/null || true

# Remove Phixr images
print_status "Removing Phixr images..."
docker rmi -f $(docker images --filter "reference=phixr*" -q) 2>/dev/null || true
docker rmi -f $(docker images --filter "reference=opencode*" -q) 2>/dev/null || true

# Remove Phixr network
print_status "Removing Phixr network..."
docker network rm phixr-network 2>/dev/null || true
docker network rm phixr-test-network 2>/dev/null || true

# Remove Phixr volumes
print_status "Removing Phixr volumes..."
docker volume rm postgres_data 2>/dev/null || true
docker volume rm redis_data 2>/dev/null || true
docker volume rm phixr-test-volume 2>/dev/null || true

# Prune unused Docker resources
print_status "Pruning unused Docker resources..."
docker system prune -f 2>/dev/null || true

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "To verify, run:"
echo "  docker images | grep -E 'phixr|opencode'"
echo "  docker network ls | grep phixr"
echo "  docker volume ls | grep phixr"
