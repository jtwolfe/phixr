# OpenCode Server for Phixr
# Pre-built image with opencode-ai installed for faster startup
FROM node:20-slim

ENV NODE_ENV=production \
    OPENCODE_TELEMETRY=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode globally
RUN npm install -g opencode-ai@latest

# Configure git defaults
RUN git config --global user.email "phixr@localhost" && \
    git config --global user.name "Phixr" && \
    git config --global init.defaultBranch main

WORKDIR /workspace

EXPOSE 4096

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=20s \
    CMD node -e "fetch('http://localhost:4096/global/health').then(r=>{process.exit(r.ok?0:1)}).catch(()=>process.exit(1))"

ENTRYPOINT ["opencode"]
CMD ["serve", "--hostname", "0.0.0.0", "--port", "4096"]

LABEL org.opencontainers.image.title="Phixr OpenCode Server" \
      org.opencontainers.image.description="OpenCode AI server for Phixr integration" \
      org.opencontainers.image.source="https://github.com/jtwolfe/phixr"
