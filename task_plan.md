# MCP Task Runner MVP Plan

## Goal
Build a small, testable AI automation execution core that plans MCP/API work, blocks non-read-only actions behind approval, verifies outcomes, and records evidence.

## Constraints
- Independent project; do not modify `windows-mcp-reliability` in this phase.
- Windows first; keep adapter interfaces portable.
- Simulated tools must run without external services.
- Feishu adapter is implemented behind an interface but disabled by default.
- No arbitrary shell execution; only explicitly allowlisted commands may be added later.

## Phases

### Phase 1: Design and skeleton
**Status:** complete
- Define tool metadata, risk policy, task lifecycle, approval interface, verification interface.
- Add model gateway configuration example.
- Add README and architecture notes.

### Phase 2: Testable core
**Status:** complete
- Implement registry, approval state machine, simulated tools, evidence events.
- Add unit tests for read-only execution and approval blocking.

### Phase 3: Windows-MCP adapter
**Status:** complete
- Add read-only streamable-HTTP adapter.
- Implement process, port, handshake, and tool-list checks.

### Phase 4: Feishu and model gateway adapters
**Status:** complete
- Add Feishu card approval adapter (disabled by default).
- Add OpenAI-compatible provider health checks and manual route config.

## Next Step
Prepare a redacted first end-to-end sandbox configuration. Before live testing, ask the user for one low-risk gateway, one model, and a non-production API key/group key through an approved secret channel.

## Decisions
- Project name remains an internal codename until the MVP works.
- All non-read-only tools require approval by default, even if metadata is incomplete.
- Verification is a separate step; a successful tool response is not task success.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| Workspace root is not a Git repository | 1 | Keep the new project isolated; inspect its own Git state before publishing. |
