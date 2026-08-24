# Memoria.ia Enterprise — Product Alpha Security Baseline

Status: alpha security baseline, **not a production security certification**

## Purpose

This document freezes the security boundary required for the first installable PC/VPS/server alpha. It records what is enforced by code, what is tested, and what remains outside the alpha guarantee.

## Trust boundaries

1. **Administrator credential** — controls organization-level administration and may access all local product scopes.
2. **Application credential** — organization-local credential restricted to declared scopes such as `memory.read`, `memory.write` and `chat.use`.
3. **Organization namespace** — memory state must not cross an organization boundary.
4. **Application namespace** — non-admin application credentials must not select another application's memory scope.
5. **Provider boundary** — external LLM providers receive only materialized context selected for the request; internal trajectory identifiers are not assumed to carry meaning outside Memoria.ia.
6. **Persistent state boundary** — memory state, application credential verifiers, non-secret configuration and provider secrets are separate artifacts.
7. **Future MA2A boundary** — certificate trust, issuance, revocation and federation are external responsibilities and are not implied by local node metadata.

## Alpha controls currently enforced

- administrative credential comparison uses `hmac.compare_digest`;
- application credentials are generated from `secrets.token_urlsafe`;
- plaintext application credentials are returned only at creation time;
- persisted application credentials use per-token salts and PBKDF2-HMAC-SHA256 verifiers;
- disabled/revoked application credentials fail authentication;
- application scopes are checked before memory/chat operations;
- application credentials cannot select a different application scope;
- organization IDs are incorporated into the product memory namespace and checked by the service boundary;
- provider credentials are not returned by public status methods;
- local alpha provider secret files are written with mode `0600` where supported;
- state manifests use integrity checks and product snapshots retain their own integrity validation;
- product backups include memory state only, explicitly exclude provider secret files, and validate SHA-256 checksums before restore;
- backup restore reads only fixed expected members and does not extract arbitrary archive paths;
- backup restore may require an expected organization ID and validates the restored service before replacing target state;
- error responses do not intentionally echo supplied credentials.

## Required alpha failure behavior

The product must fail closed for the following cases:

- missing or invalid API credential;
- application credential without the required scope;
- application credential attempting another application's scope;
- organization mismatch;
- revoked application credential;
- revoked logical memory unless explicitly requested by an authorized API path;
- corrupt product manifest/snapshot;
- corrupt or modified backup;
- backup belonging to an unexpected organization when an expected organization is supplied;
- unsupported configuration/provider identifiers.

## Secret policy

The repository and generated evidence must not contain live provider/API credentials.

Product state backup intentionally excludes:

- `product-secrets.json`;
- environment variables;
- external provider API keys;
- plaintext application tokens.

A deployment operator is responsible for backing up secret material using an appropriate independent secret-management process.

## Explicit non-guarantees

The current alpha does **not** claim:

- formal penetration-test coverage;
- resistance to a hostile local root/administrator;
- production-grade rate limiting or DDoS protection;
- enterprise SSO/OIDC/SAML;
- hardware-backed key storage;
- production secret-vault integration;
- encrypted storage at rest supplied by Memoria.ia itself;
- MA2A PKI/federation trust validation;
- multi-region high availability;
- formal supply-chain attestation;
- production readiness.

Deployments exposed to an untrusted network must therefore place the alpha behind appropriate TLS termination, firewall/network policy and deployment-level secret management.

## Gate for changing `security_status`

The API must continue to report `not-security-reviewed` until all of the following occur:

1. a written threat model is reviewed against the actual deployed topology;
2. dependency and secret-handling review is completed;
3. authentication/authorization negative tests pass from a clean checkout;
4. backup/restore corruption and organization-mismatch tests pass;
5. an external or independent security review is completed for the release candidate;
6. findings above the accepted release severity threshold are resolved or explicitly documented.

Passing product-alpha CI alone does not satisfy this gate.
