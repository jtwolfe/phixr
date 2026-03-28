# OpenCode Sandbox Container for Phixr
# Provides isolated, containerized AI code generation environment
# Based on OpenCode (https://github.com/anomalyco/opencode)

FROM node:18-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    python3 \
    python3-pip \
    npm \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (OpenCode runtime)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install OpenCode globally
RUN bun install -g opencode-ai@latest

# Create working directory
WORKDIR /workspace

# Create context mount point
RUN mkdir -p /phixr-context

# Create results directory for capturing diffs/changes
RUN mkdir -p /phixr-results

# Configure git defaults (for safe operations)
RUN git config --global user.email "phixr@localhost" && \
    git config --global user.name "Phixr Bot" && \
    git config --global init.defaultBranch main

# Set up health check for container monitoring
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD test -f /tmp/opencode.running && echo "running" || exit 1

# Environment variables for OpenCode configuration
ENV OPENCODE_MODE=build \
    OPENCODE_TELEMETRY=0 \
    OPENCODE_CONFIG_HOME=/home/opencode/.config

# Create non-root user for security
RUN useradd -m -s /bin/bash opencode
USER opencode

# Initial prompt preparation (can be overridden at runtime)
ENV OPENCODE_INITIAL_PROMPT=""

# Main entry point: OpenCode interactive mode
# Can be overridden to run in different modes:
# - Standard: opencode (interactive)
# - Server: opencode serve (for future web integration)
# - Headless: custom scripts for automated execution
ENTRYPOINT ["bash", "-c"]
CMD ["\
  # Create marker for health check \
  touch /tmp/opencode.running; \
  \
  # Clone/initialize repository if needed \
  if [ -n \"$PHIXR_REPO_URL\" ]; then \
    git clone --depth 1 \"$PHIXR_REPO_URL\" /workspace/repo && \
    cd /workspace/repo && \
    git checkout \"$PHIXR_BRANCH\" || git checkout -b \"$PHIXR_BRANCH\"; \
  fi && \
  \
  # Start OpenCode with initial prompt \
  opencode ${OPENCODE_INITIAL_PROMPT} || exit 1; \
  \
  # After OpenCode exits, capture results \
  cd /workspace/repo && \
  git diff > /phixr-results/changes.diff 2>/dev/null || true; \
  git status --porcelain > /phixr-results/status.txt 2>/dev/null || true; \
  echo $? > /phixr-results/exit_code.txt; \
  \
  # Clean up marker \
  rm -f /tmp/opencode.running \
"]

# Volume mounts (documented for docker-compose / kubernetes)
# /phixr-context - Input: mounted context (issue.json, config.json)
# /phixr-results - Output: captured diffs, status, results
# /workspace - Working directory for code changes

# Exposed ports (if needed for future web integration)
EXPOSE 8080

# Labels for identification and metadata
LABEL org.opencontainers.image.title="Phixr OpenCode Sandbox" \
      org.opencontainers.image.description="Containerized OpenCode execution environment for Phixr" \
      org.opencontainers.image.url="https://github.com/phixr/phixr" \
      org.opencontainers.image.version="0.1.0"
