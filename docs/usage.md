---
layout: default
title: Usage
---

# Usage Guide

Phixr uses three commands. Everything else is natural language.

## Commands

| Command | What It Does |
|---------|-------------|
| `@phixr-bot /session` | Start a persistent AI session for the current issue |
| `@phixr-bot /session --vibe` | Start a session and get a live OpenCode UI link |
| `@phixr-bot <any message>` | Send a message to the active session |
| `@phixr-bot /end` | Close the active session |

## Starting a Session

Comment on any GitLab issue:

```
@phixr-bot /session
```

Phixr will:
1. Extract the issue context (title, description, comments, labels)
2. Create a dedicated branch: `ai-work/issue-{id}`
3. Start an OpenCode session with the issue as its task
4. Clone the repository inside the session
5. Begin working on the issue

You'll get a confirmation comment with the session ID and branch name.

### Vibe Mode

Add `--vibe` to get a clickable link to the live OpenCode web UI:

```
@phixr-bot /session --vibe
```

This is useful for:
- Watching the AI work in real-time
- Pair programming with AI
- Debugging or reviewing the AI's approach

Multiple people can open the same link to observe the session.

## Sending Messages

Once a session is active, any `@phixr-bot` mention forwards your message to the AI:

```
@phixr-bot please add error handling to the login function
```

```
@phixr-bot looks good, but use bcrypt instead of sha256
```

```
@phixr-bot push your changes and create a merge request
```

The AI treats the full conversation as context -- it remembers everything from the issue description through all your comments.

### What Can You Ask?

The AI decides what to do based on your message. No mode selection needed:

- **Planning**: "make a plan to refactor the auth module"
- **Implementation**: "implement the changes from your plan"
- **Review**: "review the current test coverage"
- **Git operations**: "push your changes", "create an MR"
- **Iteration**: "change the database from SQLite to Postgres"
- **Questions**: "what does the `handle_session` function do?"

### No Active Session

If you mention `@phixr-bot` without an active session, Phixr will tell you and suggest starting one with `/session`.

## Ending a Session

```
@phixr-bot /end
```

This stops the OpenCode session, cleans up resources, and frees the issue for a new session.

## One Session Per Issue

Each issue can have at most one active session. If you try to start a second session on the same issue, Phixr will let you know and show the existing session's details.

To start fresh: end the current session first, then start a new one.

## Session Lifecycle

```
CREATED --> RUNNING --> COMPLETED (AI finished and went idle)
                    --> TIMEOUT (exceeded time limit)
                    --> ERROR (something went wrong)
                    --> STOPPED (user ran /end)
```

When a session completes (AI goes idle), Phixr automatically:
1. Retrieves the conversation history
2. Extracts the AI's output and any file changes
3. Posts a summary comment on the GitLab issue
4. Cleans up the session resources

## Example Workflow

```
Alice:   @phixr-bot /session --vibe
Phixr:   Session started (sess-42-a3f8e1c2)
         Branch: ai-work/issue-42
         Live Session: [Open in Browser](https://opencode.example.com/Lw/session/ses_abc123)

Alice:   @phixr-bot The login form doesn't validate email addresses.
         Can you add proper email validation and unit tests?
Phixr:   [AI works on the issue...]

         ## AI Session Complete
         Added email validation to the login form using a regex pattern.
         Added 5 unit tests covering valid emails, invalid formats,
         and edge cases.
         Files changed: 3 (+47 / -2)

Alice:   @phixr-bot looks good, push it and create an MR
Phixr:   [AI pushes and creates MR]

Alice:   @phixr-bot /end
Phixr:   Session ended.
```

## Tips

- **Be specific** -- "add JWT authentication" works better than "fix the auth"
- **Iterate** -- don't try to get everything in one message; build on the AI's work
- **Use vibe mode** for complex tasks so you can watch the approach and course-correct
- **Check the branch** -- all work happens on `ai-work/issue-{id}`, never on main
