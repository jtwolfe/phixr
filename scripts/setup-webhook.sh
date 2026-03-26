#!/bin/bash
# Setup script for GitLab webhooks
# Creates instance-level webhooks for Phixr to receive GitLab events

set -e

echo "🔗 Phixr GitLab Webhook Setup"
echo "=============================="

# Load environment variables
if [ -f ".env.local" ]; then
    source .env.local
else
    echo "Error: .env.local not found"
    exit 1
fi

# Prompt for root PAT if not set
if [ -z "$GITLAB_ROOT_TOKEN" ]; then
    echo ""
    echo "GITLAB_ROOT_TOKEN not set in .env.local"
    echo "This is required to create instance-level webhooks."
    echo "Get it from: GitLab Admin Area > Preferences > Access Tokens"
    echo ""
    read -p "Enter GitLab Root PAT: " -s GITLAB_ROOT_TOKEN
    echo ""
fi

# Configuration
GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:8000/webhooks/gitlab}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-phixr-webhook-secret}"
ROOT_TOKEN="${GITLAB_ROOT_TOKEN}"

if [ -z "$ROOT_TOKEN" ]; then
    echo "Error: GitLab Root PAT is required"
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Test GitLab connection
print_status "Testing GitLab connection..."
GITLAB_VERSION=$(curl -s --header "PRIVATE-TOKEN: $ROOT_TOKEN" "$GITLAB_URL/api/v4/version" 2>/dev/null)
if [ $? -ne 0 ]; then
    print_error "Failed to connect to GitLab. Check GITLAB_URL."
    exit 1
fi
print_status "Connected to GitLab"

# Check existing webhooks
print_status "Checking existing webhooks..."
EXISTING_HOOKS=$(curl -s --header "PRIVATE-TOKEN: $ROOT_TOKEN" "$GITLAB_URL/api/v4/hooks" 2>/dev/null)

if echo "$EXISTING_HOOKS" | grep -q "$WEBHOOK_URL"; then
    print_warning "Webhook already exists for $WEBHOOK_URL"
    
    # Get hook ID
    HOOK_ID=$(echo "$EXISTING_HOOKS" | grep -A5 "$WEBHOOK_URL" | grep '"id"' | head -1 | grep -oE '[0-9]+')
    
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Updating existing webhook (ID: $HOOK_ID)..."
        RESULT=$(curl -s --request PUT \
            --header "PRIVATE-TOKEN: $ROOT_TOKEN" \
            --header "Content-Type: application/json" \
            --data "{
                \"url\": \"$WEBHOOK_URL\",
                \"token\": \"$WEBHOOK_SECRET\",
                \"issues_events\": true,
                \"note_events\": true,
                \"job_events\": false,
                \"pipeline_events\": false,
                \"merge_requests_events\": false
            }" \
            "$GITLAB_URL/api/v4/hooks/$HOOK_ID" 2>/dev/null)
        print_status "Webhook updated"
    else
        print_status "Keeping existing webhook"
    fi
else
    # Create new webhook
    print_status "Creating instance-level webhook..."
    print_warning "URL: $WEBHOOK_URL"
    print_warning "Events: issues_events, note_events (issue comments)"
    
    RESULT=$(curl -s --request POST \
        --header "PRIVATE-TOKEN: $ROOT_TOKEN" \
        --header "Content-Type: application/json" \
        --data "{
            \"url\": \"$WEBHOOK_URL\",
            \"token\": \"$WEBHOOK_SECRET\",
            \"issues_events\": true,
            \"note_events\": true,
            \"job_events\": false,
            \"pipeline_events\": false,
            \"merge_requests_events\": false
        }" \
        "$GITLAB_URL/api/v4/hooks" 2>/dev/null)
    
    # Check if webhook was created
    if echo "$RESULT" | grep -q '"id"'; then
        HOOK_ID=$(echo "$RESULT" | grep -oE '"id":[0-9]+' | head -1 | cut -d':' -f2)
        print_status "Webhook created successfully! (ID: $HOOK_ID)"
    else
        print_error "Failed to create webhook"
        echo "Response: $RESULT"
        exit 1
    fi
fi

echo ""
echo "✅ Webhook setup complete!"
echo ""
echo "Webhook will receive:"
echo "  - Issue events (create, update, close)"
echo "  - Note events (comments on issues)"
echo ""
echo "The bot will respond when:"
echo "  - User mentions @phixr-bot in a comment, OR"
echo "  - User is assigned to an issue where phixr-bot is also assigned"
echo ""

# Save webhook ID for cleanup
if [ -n "$HOOK_ID" ]; then
    echo "$HOOK_ID" > .webhook_id
    print_status "Webhook ID saved to .webhook_id (for cleanup)"
fi
