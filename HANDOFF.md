# MCP Task Runner Handoff

> This file is the restart point for future work. Read it before changing code.

## Current State

- Status: paused after MVP and local low-risk validation.
- Repository: `https://github.com/HerShin5/mcp-task-runner`
- Branch: `main`
- Last verified commit at handoff: `48d1059 fix: harden development API authentication`
- Worktree: clean; `main` synchronized with `origin/main`.
- Verification: `133 passed`, `compileall passed`, `git diff --check passed`.

## What Is Implemented

1. Fail-closed tool registry and approval state machine.
2. SQLite approval persistence with duplicate-task protection and atomic pending-state decisions.
3. Dependency-free development API with loopback-only fallback when no API token is configured.
4. Approval callback allowlist seam; callback approver comes from `X-Approver-Id`, not JSON body.
5. Strict JSON plan parsing and local tool/risk validation.
6. Streamable HTTP MCP client with session handling, JSON/SSE decoding, Bearer auth, discovery, and read-only allowlist.
7. Windows-MCP read-only workflow: `snapshot`, `screenshot`, and `debug_nodes` only.
8. OpenAI-compatible model client and task-to-plan orchestrator.
9. Capability-aware model + gateway routing with health, pricing, quality, latency, and management metadata.
10. Management adapters, snapshot TTL, `advisory`/`required` eligibility policy, and stale-data removal.
11. Gateway failover and circuit breaker.
12. Failover guards: no replay after output starts or an external side effect may have happened.
13. Route de-duplication, actual approved-route enforcement, MCP `isError` propagation, and legacy Windows UTF-8 output handling.
14. CLI workflows: `providers-health`, `route-select`, `live-plan`, `windows-report`, and `windows-live-plan`.

## Evidence Already Obtained

- Real low-risk model sandbox: gateway health HTTP 200, target model confirmed, plan generated and locally validated, no tool execution.
- Real Windows-MCP read-only run: protocol `2025-06-18`, server `desktop-bridge 4.1.5`, 13 tools discovered, `snapshot`/`debug_nodes`/`screenshot` executed successfully, no write tool called.
- Loopback HTTP failover drill: 503/429 switched A to B; 401/403 did not switch; started-output and possible-side-effect flags did not replay; circuit recovery passed.
- Regression suite grew from 84 to 133 tests while fixing approval, routing, management, API, and failover boundaries.

## Paused Deliberately

- Do not deploy a Feishu callback to KiroForge yet.
- Do not change KiroForge DNS, Nginx, Docker, or production model configuration.
- Do not expose the development API publicly.
- Do not enable `click`, `type_text`, `key`, `launch`, PowerShell, Registry, FileSystem, or other write-capable Windows-MCP tools.
- `sandbox.providers.json` is local-only and ignored by Git. Never copy its key into docs, tests, commits, or chat.

## Remaining Work

### P0 before any public/production control plane

- Feishu webhook verification: signature, timestamp window, encrypted payload handling, replay store, and approver identity binding.
- HTTPS reverse proxy, API rate limiting, request size limits, audit retention, SQLite backup/permissions, and production secret storage.
- Separate production API configuration from the development adapter; fail closed when required security settings are missing.

### P1 engineering

- Streaming model support with an explicit pre-first-byte failover boundary and preserved route/error evidence after interruption.
- More real two-gateway sandbox drills using two approved low-risk providers; never take a production gateway down to test failover.
- Provider-specific management adapters, keeping the generic snapshot interface and manual JSON fallback.
- Observability: structured redacted audit events, request IDs, route decision reason, circuit state, and approval correlation.

### Release

- Prepare `v0.1.0` only after the P0 checklist is either implemented or explicitly marked out of scope.
- Add a redacted demo transcript and a release acceptance checklist.

## Next Resume Procedure

1. Read this file, `README.md`, `SECURITY.md`, and `task_plan.md`.
2. Run `git status -sb`, `python -m pytest -q`, and `python -m compileall -q mcp_task_runner`.
3. Choose one scoped item above; do not start Feishu deployment by implication.
4. For server/DNS/Nginx work, inspect live state and backups first; preserve existing config and provide rollback.
5. For any external gateway test, use a low-risk key through local config or a protected secret channel; never print it.
6. Add focused regression tests before changing production-facing behavior.

## Known Product Boundary

This is a safety-first, runnable MVP/research project, not yet a public production control plane. The local read-only path is validated; remote approval and public exposure remain intentionally unfinished.
