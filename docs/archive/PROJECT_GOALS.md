# Phixr Project Goals

**Last Updated**: March 28, 2026

## Vision

Phixr is a **seamless GitLab-OpenCode integration platform** that maps GitLab projects and issues directly to OpenCode projects and sessions. Users interact with AI through natural conversation in GitLab issue comments — no mode selection, no complex commands.

## Core Philosophy

- **Seamless** — GitLab issues are OpenCode sessions. Comments are messages. It should feel like talking to a colleague.
- **Minimal commands** — Three commands: `/session`, `/end`, and `@phixr <message>`. The AI figures out what to do from context.
- **Keep OpenCode's WebUI** — Preserve the clean, fast OpenCode interface. Vibe mode gives users a direct link.
- **Enterprise Ready** — External model management and privacy-first design.

## Interaction Model

### Commands

| Input | What Happens |
|-------|-------------|
| `@phixr-bot /session` | Start a persistent OpenCode session for this issue (headless). One session per issue enforced. |
| `@phixr-bot /session --vibe` | Start a session and return a live OpenCode UI link. |
| `@phixr-bot <any message>` | Forward message to the active session. AI response posted back to the issue. |
| `@phixr-bot /end` | Close the active session and release resources. |

### Key Principles

- **No mode selection** — The AI reads the issue and decides whether to plan, implement, or review. Users don't pick modes.
- **Persistent sessions** — A session stays open across multiple comments. Users can iterate: "looks good, but change the database to Postgres", "now add tests".
- **Conversational git** — Push, MR creation, and branch management happen via natural language: "push your changes", "create an MR", "discard everything".
- **One session per issue** — Prevents confusion and resource waste. Close the old session before starting a new one.

### Example Workflow

```
Alice:   @phixr-bot /session
Phixr:   🤖 AI Session Started. Session ID: sess-42-...

Alice:   @phixr-bot can you make a plan to add user authentication?
Phixr:   [posts implementation plan]

Alice:   @phixr-bot looks good, please implement it
Phixr:   [implements changes, posts summary]

Alice:   @phixr-bot push your changes and create an MR
Phixr:   [pushes to branch, creates MR, posts link]

Alice:   @phixr-bot /end
Phixr:   ✅ Session ended.
```

## Two Operating Modes

### Independent Mode (Comment-Driven)
- Purely comment-based interaction — no web UI required
- AI acts as an autonomous developer
- Creates dedicated branch per issue: `ai-work/issue-{id}`
- Posts status updates and results as GitLab comments

### Vibe Mode (Shared Visibility)
- `@phixr-bot /session --vibe` returns a direct OpenCode UI link
- Multiple users can observe the same session in real-time
- Users can interact through the OpenCode web interface directly
- "Pair programming with AI" experience

## Technical Requirements

**OpenCode Integration:**
- GitLab projects map to OpenCode projects
- GitLab issues map to OpenCode sessions (persistent, one-per-issue)
- Issue comments map to session messages
- Leverage OpenCode's HTTP API for session management
- SSE event stream for real-time monitoring

**Branch Management:**
- Every issue gets dedicated `ai-work/issue-{id}` branch
- AI handles conflicts professionally
- Clear commit history and merge request creation

**Model Management:**
- Design for external model control (future phase)
- Support local models, no hard dependencies on external services

## Success Criteria

1. **Seamless** — Interacting with Phixr feels like talking to a developer on the issue
2. **Persistent context** — The AI remembers the full conversation across comments
3. **Minimal friction** — Three commands total. Everything else is natural language.
4. **Professional git** — Clean branches, clear commits, proper MRs
5. **Fast and reliable** — Quick responses, graceful error handling

---

**Implementation Priority:**
1. Seamless session lifecycle (create, message, end)
2. Natural language command processing via `@phixr`
3. Reliable OpenCode integration with SSE monitoring
4. Professional Git operations (dedicated branches, commits, MRs)
5. Vibe mode with direct OpenCode UI links
