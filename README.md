<div align="center">
  <img src="assets/phixr-logo.png" alt="Phixr" width="200" />
  <h1>Phixr</h1>
  <p>Seamless GitLab-AI Integration Platform</p>
</div>

---

Phixr bridges GitLab's issue workflow with AI coding agents. It runs as a lightweight FastAPI service that listens for GitLab webhooks, routes `@phixr` mentions to OpenCode AI sessions, and posts results back to the issue. No context switching, no separate tools -- just comment on an issue and let the AI work.

## How It Works

```
Developer:  @phixr /session
Phixr:      Session started on branch ai-work/issue-42.

Developer:  @phixr Add input validation to the user registration endpoint
Phixr:      Working on it...
Phixr:      Done. Added validation for email, password length, and username format.
             See branch ai-work/issue-42 (3 commits).

Developer:  @phixr /end
Phixr:      Session closed.
```

## Features

- **Persistent sessions** -- one OpenCode session per GitLab issue, maintained across comments
- **Independent mode** -- AI works autonomously, posts results back to the issue
- **Vibe mode** -- `@phixr /session --vibe` returns a live OpenCode UI link for interactive collaboration
- **Automatic Git workflow** -- branch creation, commits, and merge requests handled for you
- **Multi-provider AI** -- Ollama (default), Zen, OpenAI, or any OpenAI-compatible provider
- **Redis state management** -- scalable session tracking for multi-user deployments

## Quick Start

```bash
git clone https://github.com/your-org/phixr.git && cd phixr
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local   # edit with your GitLab URL, tokens, etc.
python -m phixr.main
```

For full setup instructions including GitLab webhook configuration, see the [Getting Started guide](https://your-org.github.io/phixr/getting-started/).

## AI Providers

Phixr works with any OpenAI-compatible provider. Configure via environment variables:

```bash
# Ollama (default, local)
OPENCODE_PROVIDER=ollama
OPENCODE_MODEL=qwen2.5-coder:32b

# Zen
OPENCODE_PROVIDER=zen
OPENCODE_API_KEY=your-zen-key
OPENCODE_MODEL=anthropic/claude-sonnet-4-20250514

# OpenAI
OPENCODE_PROVIDER=openai
OPENCODE_API_KEY=your-openai-key
OPENCODE_MODEL=gpt-4o
```

## Documentation

Full documentation at [https://your-org.github.io/phixr/](https://your-org.github.io/phixr/)

## License

License: TBD
