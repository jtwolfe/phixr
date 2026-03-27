#!/bin/bash
# Script to add GitLab SSL certificate to trusted certificates
# This fixes HTTPS git clone issues with self-signed certificates

set -e

GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
CERT_FILE="/usr/local/share/ca-certificates/gitlab.crt"

echo "Setting up GitLab SSL certificate trust..."

# Extract hostname from URL
if [[ $GITLAB_URL =~ ^https?://([^:/]+) ]]; then
    GITLAB_HOST="${BASH_REMATCH[1]}"
else
    echo "Invalid GITLAB_URL: $GITLAB_URL"
    exit 1
fi

echo "GitLab host: $GITLAB_HOST"

# Wait for GitLab to be available
echo "Waiting for GitLab to be available..."
timeout=60
counter=0
while ! curl -k -s "$GITLAB_URL" > /dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $timeout ]; then
        echo "GitLab not available after $timeout seconds, continuing anyway..."
        break
    fi
    echo "Waiting for GitLab... ($counter/$timeout)"
    sleep 1
done

# Check if GitLab uses HTTPS
if [[ $GITLAB_URL =~ ^https:// ]]; then
    echo "GitLab uses HTTPS, setting up SSL certificate..."

    # Get SSL certificate from GitLab
    if ! openssl s_client -connect "${GITLAB_HOST}:443" -servername "$GITLAB_HOST" < /dev/null 2>/dev/null | openssl x509 -outform PEM > "$CERT_FILE" 2>/dev/null; then
        echo "Failed to download certificate from ${GITLAB_HOST}:443"
        echo "GitLab might not be using standard HTTPS, continuing..."
    else
        echo "Certificate downloaded successfully"

        # Update CA certificates
        update-ca-certificates
    fi
else
    echo "GitLab uses HTTP, no SSL certificate needed"
fi

# Configure git to be more permissive with SSL for GitLab hosts (for development)
# Add multiple host patterns to cover all variations
for host in "172.17." "127.0.0.1" "localhost" "gitlab.local" ":8080"; do
    git config --global --add "http.${host}.sslVerify" false
done

# Configure git credential handling to prevent username prompts
git config --global credential.helper ""
git config --global http.sslVerify false

# Set up credential helper that never prompts
cat > /usr/local/bin/git-credential-neverprompt << 'EOF'
#!/bin/bash
echo "username=oauth2"
echo "password=dummy"
exit 0
EOF
chmod +x /usr/local/bin/git-credential-neverprompt
git config --global credential.helper "/usr/local/bin/git-credential-neverprompt"

echo "Git SSL and credential configuration completed"
echo "Git config summary:"
git config --global --list | grep -E "(http|credential)" | cat

echo "GitLab SSL certificate setup complete"