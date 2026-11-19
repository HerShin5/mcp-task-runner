# Security Notes

## Secret handling

Never commit:

- model API keys;
- gateway management tokens;
- MCP bearer tokens;
- group keys;
- Feishu app secrets;
- live provider configuration.

Use environment variables or a local secret store. Keep only redacted examples in the repository.

## Execution safety

The runner defaults to read-only execution. Any write or destructive tool requires an approval gateway. Approval does not make a tool safe by itself: the tool must still be explicitly registered and its result must be verified.

Do not enable arbitrary shell execution in production. Future shell support must use an allowlist, argument validation, approval, timeout, and an idempotency key.

## Gateway safety

Provider health and management data are untrusted observations. Do not treat a provider's own status as proof that an action succeeded. Record the selected route, response status, latency, and verification result.

Do not use a browser session cookie as the long-term product credential for a gateway management adapter. Obtain an explicitly authorized API credential and store it outside Git.

## Reporting

Do not publish credentials or private gateway responses in issues. Redact tokens, emails, account IDs, IP addresses, and private usage data before sharing evidence.
