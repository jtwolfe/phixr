# OpenCode Sandbox Container for Phixr - Production Version
# Provides isolated, containerized AI code generation environment
FROM node:20-slim

ENV NODE_ENV=production \
    OPENCODE_TELEMETRY=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash opencode

WORKDIR /workspace

RUN npm install -g opencode-ai@latest && \
    ln -sf /usr/local/lib/node_modules/opencode-ai/bin/opencode /usr/local/bin/opencode

RUN mkdir -p /home/opencode/.config/opencode && \
    mkdir -p /workspace /phixr-context /phixr-results

# Create OpenCode configuration for zen provider
# Using "opencode" as the provider ID for Zen models
RUN printf '{\n' > /home/opencode/.config/opencode/opencode.json && \
    printf '  "$schema": "https://opencode.ai/config.json",\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '  "model": "opencode/big-pickle",\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '  "provider": {\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '    "opencode": {\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '      "options": {\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '        "apiKey": "{env:OPENCODE_ZEN_API_KEY}",\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '        "baseURL": "https://opencode.ai/zen/v1"\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '      }\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '    }\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '  }\n' >> /home/opencode/.config/opencode/opencode.json && \
    printf '}\n' >> /home/opencode/.config/opencode/opencode.json

RUN git config --global user.email "phixr-bot@localhost" && \
    git config --global user.name "Phixr Bot" && \
    git config --global init.defaultBranch main && \
    chown -R opencode:opencode /home/opencode /workspace /phixr-context /phixr-results

USER opencode

ENV PHIXR_REPO_URL="" \
    PHIXR_BRANCH="main" \
    OPENCODE_MODE=build

ENTRYPOINT ["node", "/usr/local/lib/node_modules/opencode-ai/bin/opencode"]
CMD ["--help"]
