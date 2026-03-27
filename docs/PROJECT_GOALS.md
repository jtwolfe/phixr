# Phixr Project Goals

**Last Updated**: March 27, 2026

## Vision

Phixr is a **hybrid Git-integrated collaborative AI coding platform** that provides natural language AI assistance directly within GitLab while leveraging OpenCode's excellent web UI for interactive coding sessions.

## Core Philosophy

- **Keep OpenCode's WebUI** - Preserve the clean, fast, and powerful OpenCode interface that users love
- **GitLab-native Experience** - Users should be able to interact with AI primarily through natural language comments
- **Two Distinct Modes** - Support both automated and collaborative workflows
- **Enterprise Ready** - External model management and privacy-first design

## Primary Goals

### 1. Natural Language GitLab Integration
- Users interact with AI primarily through natural language comments using `@phixr`
- The AI should understand context-aware commands and respond appropriately
- **Example Interactions**:
  - `@phixr can you make a plan to resolve this issue?`
  - `@phixr please implement this plan`
  - `@phixr can you update the tests so that the build works?`
  - `@phixr what would be involved in adding user authentication?`
  - `@phixr review this code and suggest improvements`

**AI Behavior**: The AI should act like a competent, professional developer colleague - proactive, thoughtful, and collaborative. It should ask clarifying questions when needed and provide clear explanations of its approach.

### 2. Two Distinct Operating Modes

The system must clearly distinguish between automated and collaborative workflows:

#### Independent Mode (Comment-Driven Automation)
- **Purely comment-based interaction** - no web UI required
- AI acts as an autonomous professional developer
- **Automatic Actions**:
  - Creates dedicated feature branch per issue: `ai-work/issue-{id}`
  - Analyzes the issue and creates comprehensive plans when requested
  - Implements changes with clear, atomic commits
  - Pushes changes to the branch
  - Creates well-formatted merge requests
  - Handles merge conflicts professionally (like an experienced developer)
- Posts status updates, plans, and results as GitLab comments
- **Goal**: Feels like working with a reliable, competent developer colleague

#### Vibe Mode (Shared Visibility)
- Creates a **unified web interface** for collaborative observation
- Uses OpenCode's excellent web UI (preserved as-is)
- **Shared Session Model** (not true multi-user editing):
  - Multiple users can view the same OpenCode session
  - Real-time visibility: when User 1 types, User 2 sees the changes
  - Both users can observe AI actions in real-time
  - Users can take turns interacting with the interface
- Provides a "pair programming with AI" experience that can be shared
- **Goal**: Collaborative workspace where team members can observe and participate

### 3. GitLab Web IDE-like Experience

The system should provide an experience similar to GitLab's web IDE but enhanced with AI capabilities:

- **Branch-specific Environments**: Each issue gets a dedicated workspace at the correct branch state
- **Automatic Setup**: When AI is invoked, it:
  - Ensures the `ai-work/issue-{id}` branch exists
  - Clones/checks out the repository at the appropriate state
  - Loads the full project context
  - Injects issue details and requirements
- **Seamless Workflow**: Users can seamlessly move between:
  - GitLab comments (natural language requests)
  - Web UI (interactive coding with OpenCode)
  - Git operations (commits, branches, MRs)
- **Professional Development Practices**: AI should follow:
  - Clear commit messages
  - Logical branch organization
  - Proper testing and validation
  - Professional code review standards

This creates a unified development experience that feels natural and productive.

### 4. Technical Requirements

**OpenCode Integration:**
- Leverage OpenCode's web UI and agent capabilities
- Use file-based context injection where HTTP API is unreliable
- Maintain session isolation per issue/branch

**Model Management:**
- Design for external model control (to be implemented later)
- Support local models and avoid sending code to third parties
- Make model configuration extensible

**Branch Management:**
- Every issue gets its own dedicated branch
- AI handles conflicts professionally
- Clear commit history and merge request creation

### 5. Non-Functional Requirements

- **Performance**: Fast response times, smooth web UI
- **Reliability**: Robust error handling, graceful degradation
- **Usability**: Natural, intuitive interaction patterns
- **Maintainability**: Clean, well-documented architecture
- **Scalability**: Support multiple concurrent sessions

## Success Criteria

The system is successful when:

### Functional Requirements
1. **Natural Language Processing**: Users can give natural language commands to `@phixr` and receive appropriate responses
2. **Independent Mode**: AI can autonomously handle issues end-to-end (planning → implementation → MR creation)
3. **Vibe Mode**: Provides a unified web interface where multiple users can observe and interact with the same OpenCode session
4. **Git Operations**: AI automatically manages branches, commits, and merge requests professionally
5. **OpenCode Integration**: Preserves and leverages OpenCode's excellent web UI without compromising its quality

### User Experience Requirements
- The AI feels like working with a **competent, professional developer colleague**
- Interactions are **natural and intuitive**
- The system is **fast and responsive**
- **Context is maintained** across interactions
- **Error handling** is graceful and informative

### Technical Requirements
- **Reliability**: Robust error handling with graceful degradation
- **Performance**: Fast response times and smooth web UI experience
- **Maintainability**: Clean, well-documented, and extensible architecture
- **Privacy**: Designed with enterprise requirements in mind (model control extensibility)

---

**This document represents the current and authoritative project direction.**

**Implementation Priority**:
1. Two-mode system (Independent + Vibe modes)
2. Natural language GitLab command processing with @phixr
3. Reliable OpenCode integration using file-based context injection
4. Professional Git operations (dedicated branches, clear commits, MRs)
5. Clean architecture that supports future external model management

**Repository Structure**: Documentation has been reorganized with only `README.md` in the root and all other documentation in the `docs/` directory for cleanliness.

## Technical Constraints & Considerations

- **OpenCode WebUI**: Must be preserved - do not rebuild or significantly modify the UI
- **HTTP API Limitations**: Use file-based context injection as primary method due to current API issues
- **Branch Strategy**: Every issue gets dedicated `ai-work/issue-{id}` branch
- **Model Management**: Design system to support external model control (Phase 2.5)
- **Enterprise Ready**: Privacy-first design, no hard dependencies on external services
