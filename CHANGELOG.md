# Changelog

## Unreleased

- Chinese-first repository landing page with an English README available at `README.en.md`.
- Clarified that model, gateway, API key, Base URL, group key, and management credentials are user-provided configuration.
- Added CI, MIT license, architecture, security, and contribution documentation.
- Added a provider-neutral management snapshot seam and optional catalog fixture loading.
- Management snapshots now affect ordinary and joint model/gateway routing with fail-closed group/model filtering, multiplier-aware cost, and error-rate penalties.
- Added a runtime management adapter protocol, generic JSON HTTP adapter, and TTL-backed snapshot store that drops stale data after refresh failures.
- Routed the health and route-selection CLI commands through `GatewayCatalog`, with one catalog method for consistent joint model/gateway selection.

## 0.1.0 MVP

- Safety-first tool registry and fail-closed approval flow.
- MCP Streamable HTTP read-only client and Windows-MCP diagnostic plan.
- Dynamic model/gateway catalog with cost, health, balance, latency, and quality signals.
- Capability-aware model selection and fixed benchmark contracts.
- Structured planner validation before any execution.
