# Security

## Authentication status

- `AUTH_MODE=development` accepts `X-Tenant-Id` / `X-Actor-Id` headers for local use.
- **Development auth is NOT production-safe.**
- Production design: Microsoft Entra ID placeholders and managed identity for Azure services.

## Secret handling

- API keys are stored only as backend credential references.
- Frontend may create/update credential references but never retrieves secret values.
- Audit snapshots redact keys/tokens/passwords.
- Structured logs must not emit secrets.

## File-upload security

- Max upload size enforced.
- Extension/MIME consistency checks for dangerous mismatches.
- Safe filename handling (path segments stripped).
- Archive expansion limits reserved for future archive formats.

## Tenant isolation

Every durable record carries `tenant_id`. Access helpers reject cross-tenant reads.

## External provider data rules

- `ALLOW_EXTERNAL_LLM_FOR_SENSITIVE_DOCS` gates cross-provider use.
- Failover is prohibited for sensitive docs when cross-provider failover is disabled.
- SVG delivery uses allowlist sanitization; only sanitized SVG is shown in the UI.

## Production-hardening checklist

- [ ] Disable development auth
- [ ] Configure Entra ID
- [ ] Key Vault references for all secrets
- [ ] Network isolation / private endpoints
- [ ] WAF / rate limiting at edge
- [ ] Container image scanning (Trivy) in CI
- [ ] Dependency vulnerability scanning
- [ ] Rotate credentials
- [ ] Confirm `OPTIMIZATION_ALLOW_AUTOMATIC_EXECUTION=false`
