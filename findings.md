# Findings

## Existing foundation
- Existing local project: `workspace/windows-mcp-reliability`, a Python 3.14+ MIT fork of Windows-MCP.
- The fork already contains a read-only `windows-mcp doctor` command and tests. This project should consume it later through an adapter, not duplicate its implementation.

## Product boundary
- This project is an AI-driven task execution core, not a Dify clone and not a drag-and-drop workflow editor.
- The differentiator is the execution safety loop: plan -> classify risk -> approve when required -> execute -> verify -> record evidence.

## Borrowed ideas to formalize
- MCP tool registry with explicit read-only/destructive metadata.
- Skill-like repeatable task artifacts and acceptance evidence.
- Model provider configuration with manual endpoint/model fallback.

## Untrusted research notes
- Third-party model groups may represent official API relays, account-based routes, protocol adapters, or marketing labels. Provider health checks must record source/compatibility/risk rather than trusting a group name.

## Generic management-plane discovery
- A browser-authenticated gateway management UI exposed read-only endpoints for dynamic group records, model availability, rate multipliers, active status, long-context pricing flags, fallback identifiers, RPM limits, channel health, TTFT, cache/error rates, RPM/TPM, model usage, actual cost, balance, frozen balance, account concurrency, and notification settings.
- Browser session authentication must not be shipped as a product credential. A future adapter needs an explicitly authorized management API token/configuration; secrets stay outside Git.
- Direct evidence for current in-flight concurrency may be incomplete. RPM/TPM and a local semaphore are safe fallbacks until a provider exposes a live concurrency field.

## Gateway access prerequisites
- Providers may require egress IP allowlisting, a compatible User-Agent, a group key, a management token, or special headers. The adapter must distinguish `blocked_by_allowlist`, `invalid_api_key`, `model_unavailable`, `gateway_unreachable`, and `healthy` instead of collapsing all failures into one status.
