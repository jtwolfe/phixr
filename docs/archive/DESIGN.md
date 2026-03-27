<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="250" />
</div>

# High-Level Design Document: Phixr
## Hybrid Git-Integrated Collaborative AI Coding Platform

**Version:** 1.0 (Draft)  
**Date:** March 25, 2026  
**Author:** Grok (synthesized from collaborative ideation)  
**Status:** High-Level Design – ready for detailed architecture, MVP scoping, and implementation planning

---

## 1. Executive Summary
Phixr is an **open-core, self-hosted hybrid AI coding agent** that bridges the structured world of GitLab / GitHub / Gitea issues/epics with the fluid, "vibey" personal-agent experience of tools like OpenCode or Aider.

It lives natively inside your VCS web UI while offering a real-time collaborative browser-based "vibe room" for deep work. Users start tickets exactly as they do today (`/ai-vibe <invite-id>`), then jump into a multi-user web environment where they pair/mob with the AI (and each other) using natural chat, shared editor, terminal, and optional video.

When ready, the AI takes over in a secure sandbox, implements changes, and ships a polished MR/PR back to the original issue with full session history preserved as a Git artifact.

**Core value proposition:**
- Zero-friction team adoption (works from the issue tracker everyone already lives in).
- Fun, real-time collaborative "vibe coding" with AI.
- Full privacy & cost control (local/open models).
- Turns expensive proprietary tools (GitLab Duo, Traycer.ai, etc.) into an open, superior, self-hosted alternative.

Target users: individual devs, small teams, and enterprises running self-hosted GitLab CE/EE, Gitea/Forgejo, or GitHub Enterprise.

---

## 2. Objectives & Problem Statement
**Problems solved**
- GitLab Duo and similar tools are expensive, credit-gated, and locked-in.
- Existing agents are either terminal-only (great for solo but invisible to teams) or UI-only bots (no real-time collaboration).
- No seamless bridge between "create issue → assign to AI" and "deep collaborative coding session."
- Session history and decisions are lost; audits are painful.
- Multi-dev + AI pair-programming is clunky across separate tools.

**Key goals**
- Hybrid workflow: structured VCS bot + vibey collaborative web environment.
- Multi-user real-time sessions with flattened AI context but human-visible attribution.
- Full Git-native automation (sandbox → fork/branch → MR with tests).
- Session artifacts stored permanently in the repo/issue.
- Open-core + paid org subscriptions for team-scale features.
- Local-first with optional cloud model fallback.

---

## 3. High-Level Architecture
Phixr is a **lightweight Docker-first service** that runs alongside your self-hosted Git provider.

**Core Components**
1. **Webhook Gateway** – Listens to GitLab/GitHub/Gitea webhooks (issue comments, assignments, labels, MR events).
2. **Conversation Engine** – LLM orchestration layer (LangGraph / CrewAI style) using local models via Ollama/vLLM or any OpenAI-compatible endpoint.
3. **Vibe Room Server** – Real-time WebSocket backend managing sessions, collab state, and invite codes.
4. **Sandbox Engine** – Ephemeral Docker/Kubernetes pods for safe code execution (git clone, edit, test, commit).
5. **RAG Context Store** – Vector DB (Chroma / Qdrant) + repo indexer that pulls full code + issue/epic history.
6. **Frontend** –
   - Minimal GitLab-style comment renderer (for bot replies).
   - Full browser Vibe Room: Monaco editor + xterm.js terminal + chat pane + Jitsi video embed.
7. **Artifact & Persistence Layer** – PostgreSQL (or SQLite for single-node) + Git API for committing session transcripts.
8. **Session Manager** – Redis for real-time state and short-lived invite codes.

**Deployment models**
- Single-node Docker Compose (dev / small team).
- Multi-node Kubernetes (org scale).
- Fully air-gapped.

---

## 4. Detailed Features (Comprehensive)
### 4.1 VCS-Native Bot Layer (Structured Entry Point)
- Install as GitLab App / Project Hook / Gitea webhook (OAuth2 + personal token fallback).
- Slash commands in any issue/epic comment:
  - `/ai-vibe <invite-id>` → creates & links a vibe session.
  - `/ai-plan`, `/ai-implement`, `/ai-review-mr`, `/ai-fix-tests`, `/ai-abort`.
- Natural multi-turn conversation inside issue comments (AI replies with markdown, plans, questions, code snippets).
- Automatic context injection: full issue thread + parent epic + linked issues + milestone + labels.
- Epic awareness: can update child issues, move cards on boards, set statuses, comment on parents.
- MR/PR automation: auto-generates title, description, checklist, test results; starts as Draft; adds labels ("ai-generated").

### 4.2 Vibe Room – The Collaborative "Vibey" Environment
- Browser-based real-time session (no local install required).
- Pre-populated with: issue/epic context + latest code from fork/branch + full RAG index.
- **Multi-user support** (core innovation):
  - Any number of users join via shareable invite-id link (expires after 24 h or manual close).
  - Chat pane shows prefixed messages: `user(jim):` / `user(jane):` for humans.
  - Messages are **flattened** to the LLM as a single clean "User:" stream to keep context coherent.
  - Real-time collaborative editor (Yjs/CRDT or Liveblocks-style) – multiple cursors, shared terminal.
  - Optional embedded video chat (self-hosted Jitsi Meet – zero extra auth).
- Session persistence: can be resumed any time before close.
- Built-in terminal pane with AI-assisted commands (same feel as OpenCode TUI but in browser).
- LSP integration for smart completions inside the shared editor.
- Mobile-friendly read-only view for quick reviews.

### 4.3 Implementation & Sandbox Flow
- Triggered by `/ai-implement` (inside vibe room or issue).
- Spins up isolated Docker sandbox (or K8s pod).
- Git-native operations (Aider-style diff editing, smart commits, branch management).
- Configurable output target: new branch in same repo **or** user-owned fork (safer for strict permissions).
- Runs tests, linting, build steps from your repo's CI config.
- Human approval gate before final push/MR creation (configurable per-project).
- Full audit log of every sandbox action.

### 4.4 Artifact & History Management
- On session close (or manual `/ai-archive`):
  - Entire chat transcript + AI reasoning + diffs + decisions rendered as Markdown.
  - Committed to the MR branch **or** attached as issue/MR comment/artifact.
  - Optional Git note or dedicated `.ai-sessions/` folder for long-term history.
- Full message history is searchable via the bot later ("show me the vibe session for issue #123").

### 4.5 Safety, Security & Guardrails
- Sandbox is network-isolated except to your Git provider and allowed package registries.
- Secret redaction (scans for tokens, passwords).
- Permission prompts before any git push or destructive action.
- Rate limiting and usage quotas per org/user.
- Read-only mode for guests.
- Audit trail of every AI action stored in DB and linked to sessions.

### 4.6 Team / Org Features (Paid Tier)
- Multi-tenant dashboard: live session list, usage analytics, time-saved reports.
- SSO, SCIM, role-based permissions.
- Concurrent session limits and priority queuing.
- Webhook integrations (Slack/Teams notifications on session start/complete).
- Usage analytics export for manager reporting.
- Custom fine-tuning / model hosting options.

### 4.7 Extensibility & Plugins
- Custom tools inside vibe rooms ("@run-my-test-suite", "@sync-jira").
- Plugin system for additional VCS providers or external services.
- API for embedding vibe rooms in other tools.

---

## 5. User Workflows (End-to-End Examples)
1. **Solo quick fix**: Create issue → `/ai-vibe solo-xyz` → vibe alone in browser → `/ai-implement` → MR created.
2. **Team mob session**: PM creates epic → dev runs `/ai-vibe team-warroom` → 3 devs + AI jump in with video → collaborative coding → ship MR → transcript attached to epic.
3. **Manager oversight**: Stakeholder joins vibe room in read-only mode, watches real-time, adds comments that get prefixed and sent to AI.

---

## 6. Data Model (High-Level)
- **Sessions** table: id, invite_code, issue_id, vcs_provider, status, participants[], created_at.
- **Messages** table: session_id, sender_type (human/ai), raw_text, prefixed_text, timestamp.
- **Artifacts** table: session_id, markdown_content, git_commit_sha, attached_to (issue/mr).
- **RAG Index**: per-repo embeddings (code files + issue history).

---

## 7. Non-Functional Requirements
- **Performance**: < 2 s response for bot replies; real-time collab latency < 200 ms.
- **Scalability**: Horizontal scaling via Kubernetes; handle 100+ concurrent vibe rooms.
- **Privacy**: All data stays on-prem; no telemetry by default.
- **Reliability**: Sandbox timeouts, automatic retries, session resume on crash.
- **Accessibility**: WCAG 2.1 AA compliance for web UI.

---

## 8. Recommended Technology Stack (Flexible)
- **Backend**: Python (FastAPI) or Go (for performance).
- **LLM**: Ollama / vLLM + local models (Qwen2.5-Coder, Mistral, Llama 3.1).
- **Frontend**: Next.js / React + Monaco + xterm.js + Yjs.
- **Real-time**: WebSockets + Redis.
- **Sandbox**: Docker-in-Docker or Kaniko + security profiles.
- **Storage**: PostgreSQL + Qdrant.
- **Video**: Self-hosted Jitsi.
- **Base fork candidates**: OpenCode server + Sweep AI logic + Aider git layer.

---

## 9. Open-Core & Monetization Strategy
- **Free OSS core**: Single-user vibe sessions, basic bot, local models, one repo.
- **Paid org tier** ($15–40/user/mo or flat server license): multi-user rooms, video, dashboard, SSO, analytics, priority support, unlimited concurrent sessions.
- **Enterprise add-ons**: air-gapped support, custom model hosting, dedicated SLA.

---

## 10. Risks & Next Steps
- **Risks**: Sandbox security hardening, real-time collab state conflicts, LLM context window management on very large repos.
- **Next steps**:
  1. Detailed architecture diagram (sequence + component).
  2. MVP scope (core bot + single-user vibe room + GitLab integration).
  3. POC prototype (2–3 weeks).
  4. Open-source repo setup.

This design is ready for deep-dive into any section. Want me to expand any part into low-level specs, draw Mermaid architecture diagrams, or generate starter Docker-compose + webhook code? Just say the word and we'll keep building. 🚀
