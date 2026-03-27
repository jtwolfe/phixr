#!/bin/bash
echo "Checking Phixr logs for session creation..."
docker compose logs phixr-bot --tail=30 | grep -E "(Plan session|OpenCode session|Created UI-embedded|vibe|session|Failed to start)" | tail -10

echo ""
echo "Checking sandbox health..."
curl -s http://localhost:8000/api/v1/sandbox/health

echo ""
echo "Checking vibe rooms..."
curl -s http://localhost:8000/api/v1/vibe/rooms
