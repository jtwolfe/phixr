# OpenCode + GitLab Integration: Test & Integration Plan

**Status**: ACTIVE | **Last Updated**: 2026-03-26 | **Owner**: Phixr Bot

This document outlines the complete plan for integrating OpenCode's AI coding capabilities with GitLab's issue management system, with a focus on "vibe coding" collaborative sessions.

## Architecture Overview

We are building a bridge between:
- **GitLab**: Issue tracking, MRs, comments, webhooks
- **OpenCode**: AI coding agent with planning mode and web UI
- **Phixr**: Our orchestration layer that ties everything together

**Core Principle**: "Cut open" OpenCode to stitch its functionality into GitLab workflows while embedding its web UI for collaborative coding.

## Available Credentials (GitLab Test Environment)

- **Root User**: Use `GITLAB_ROOT_TOKEN` from `.env.local`
- **Phixr Bot**: Use `GITLAB_BOT_TOKEN` from `.env.local`
- **GitLab URL**: `http://localhost:8080`
- **Test Projects**: Available in the test GitLab instance

**Testing Mandate**: ALL functionality MUST be tested against the real GitLab test environment, not mocked.

## Phased Implementation Plan

### Phase 0: Research & Validation (COMPLETED)

**Objective**: Deep understanding of OpenCode architecture and integration points.

**Activities**:
- Analyzed OpenCode source in `opencodecode/opencode/`
- Documented session management, planning mode, and web UI
- Identified reuse opportunities vs custom implementation needs
- Created this comprehensive test and integration plan

**Success Criteria**:
- [x] Complete architecture mapping
- [x] Documented OpenCode APIs and session model
- [x] Test scenarios defined
- [x] Integration strategy validated

**Test Results**: OpenCode has built-in planning mode (Tab key), session sharing via `/s/[id]`, and a client/server architecture that can be leveraged.

---

### Phase 1: Core Session Bridge

**Objective**: Create clean abstraction layer between GitLab and OpenCode.

**Components to Build**:

1. **`phixr/git/branch_manager.py`**
   - Smart branch detection for issues
   - MR-aware branch selection
   - Procedural branch naming (`ai-work/issue-{id}`)

2. **Enhanced `ContextExtractor`**
   - Include branch information
   - Full conversation history
   - GitLab context enrichment

3. **`SessionBridge` Service**
   - Orchestrates OpenCode session creation
   - Context injection with GitLab data
   - Session lifecycle management

**Testing Requirements**:
- Test with real GitLab instance using root/phixr-bot PATs
- Verify branch detection works for issues with/without MRs
- Validate context injection includes full conversation
- Track outcomes in `test-results-phase1.md`

**Success Criteria**:
- [ ] BranchManager correctly identifies existing work
- [ ] Context extraction includes branch + conversation data
- [ ] Sessions created with correct branch context
- [ ] All tests pass against real GitLab environment

**Tracking**: Create `docs/oc-testandinteg/test-results-phase1.md` with test cases and outcomes.

---

### Phase 2: Planning Workflow

**Objective**: Fix perpetual planning and implement proper plan generation.

**Components**:

1. **Background Plan Monitoring**
   - Run `monitor_plan_completion()` as real async task
   - Better plan completion detection
   - Plan extraction and GitLab posting

2. **Enhanced Planning Prompts**
   - Use OpenCode's built-in planning capabilities
   - Include full context and conversation
   - Clear instructions for structured output

3. **`/ai-plan` Command Handler**
   - Complete workflow from GitLab comment to OpenCode
   - Proper error handling and status updates

**Testing Requirements**:
- Test `/ai-plan` command end-to-end with real GitLab issue
- Verify plan is generated and posted back to GitLab
- Test with different issue types and conversation lengths
- Document all test outcomes truthfully

**Success Criteria**:
- [ ] `/ai-plan` creates session and starts monitoring
- [ ] Plans are properly generated and returned to GitLab
- [ ] Background monitoring works reliably
- [ ] Error cases are logged to both UI and GitLab

**Tracking**: `docs/oc-testandinteg/test-results-phase2.md`

---

### Phase 3: Vibe Room & Close-Out Workflow

**Objective**: Complete collaborative coding experience.

**Components**:

1. **Enhanced Vibe Room UI**
   - "Close Out & Commit" button
   - Real-time status updates
   - Error display

2. **CloseOut Workflow**
   - Git commit of all changes
   - Push to appropriate branch
   - Session and repository cleanup
   - Status reporting to GitLab

3. **Error Recovery**
   - If push fails, leave session open
   - Ask OpenCode to resolve git issues
   - Log errors to both interfaces

**Testing Requirements**:
- Test complete vibe room workflow end-to-end
- Verify commit/push works with real GitLab
- Test error scenarios (failed push, network issues)
- Validate cleanup works properly

**Success Criteria**:
- [ ] Users can work in embedded OpenCode UI
- [ ] Close-out properly commits and pushes changes
- [ ] Error handling follows requirements
- [ ] Session cleanup is reliable

**Tracking**: `docs/oc-testandinteg/test-results-phase3.md`

---

### Phase 4: Implementation Workflow & Polish

**Objective**: Complete the full development cycle.

**Components**:

1. **`/ai-implement` Command**
   - Takes plan from previous session
   - Executes implementation
   - Handles the build phase

2. **MR Creation & Integration**
   - Create MRs when appropriate
   - Link back to original issues
   - Update issue status

3. **Comprehensive Monitoring**
   - Health checks and status
   - Error tracking and reporting
   - Performance monitoring

4. **Documentation & Testing**
   - Complete test suite
   - Usage documentation
   - Production readiness

**Testing Requirements**:
- End-to-end test: issue → plan → implement → commit → MR
- Test all error scenarios
- Performance and reliability testing
- Real GitLab environment validation

**Success Criteria**:
- [ ] Complete workflow from issue to MR
- [ ] All components work together reliably
- [ ] Comprehensive test coverage
- [ ] Production-ready implementation

**Tracking**: `docs/oc-testandinteg/test-results-phase4.md`

---

### Phase 5: Production Hardening

**Components**:
- Security review and hardening
- Configuration management
- Monitoring and observability
- Performance optimization
- Documentation completion

**Final Testing**:
- Load testing
- Failure scenario testing
- Integration testing with real workflows
- User acceptance testing

## Test Tracking Methodology

For each phase, we will maintain:

1. **`test-results-phaseN.md`**: Detailed test cases and outcomes
2. **GitLab Issues**: Use the test GitLab instance for real testing
3. **Success Metrics**: Clear pass/fail criteria for each component
4. **Error Logs**: All errors must be documented with reproduction steps
5. **Screenshots/Logs**: Evidence of successful test runs

**Truthful Reporting Mandate**: All test results must be honest. Failed tests must be documented with failure reasons and not glossed over.

## Credentials & Environment

- **GitLab**: `http://localhost:8080`
- **Root PAT**: Available in `.env.local` as `GITLAB_ROOT_TOKEN`
- **Bot PAT**: Available in `.env.local` as `GITLAB_BOT_TOKEN`
- **Test Projects**: Use projects in the test GitLab instance
- **OpenCode**: Running at `http://localhost:4096`

## Success Definition

The integration is complete when:
1. `/ai-plan` works end-to-end with real GitLab issues
2. Vibe rooms support collaborative coding with proper close-out
3. Branch management works intelligently
4. All errors are properly handled and logged
5. Complete test documentation exists with real test results
6. The system is production-ready

---

**This document will be updated as each phase is completed with test results and findings.**

**Current Status**: Phase 0 and Phase 1 COMPLETED. All core infrastructure is built and tested.

**Next Action**: Proceed with Phase 2 (Planning Workflow) implementation.

**Test Results Summary**: 
- Phase 0: ✅ Complete architecture analysis and planning
- Phase 1: ✅ BranchManager, enhanced ContextExtractor, Session integration, and Vibe Room close-out all implemented and tested
- All tests pass against real GitLab environment (with appropriate error handling for test data)