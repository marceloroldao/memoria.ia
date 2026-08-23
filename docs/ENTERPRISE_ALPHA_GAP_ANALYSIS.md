# Memoria.ia Enterprise — Product Alpha Gap Analysis

Status: active product alpha
Target: PC / VPS / server
Stable memory baseline: `v0.95.1`
Experimental research line: `experiment/v0.96-semantic-routing`
Product branch: `product/enterprise-alpha`

## Evidence rule

This document separates demonstrated code from experiments, hypotheses, external dependencies, and production-hardening work. Product-alpha PASS means that a capability has reproducible repository evidence; it is not a production-security or general-performance guarantee.

## Current baseline

Memoria.ia now has two deliberately separated tracks:

1. a stable/research memory core derived from the validated v0.95 line, with routed lifecycle memory, trajectory-based known-route resolution and snapshot persistence; and
2. an incremental PC/server product layer on `product/enterprise-alpha`, which wraps that core with organization boundaries, HTTP, credentials, persistence/restart, web UI, provider-neutral LLM integration, instrumentation, container deployment and acceptance gates.

Semantic routing v0.96 remains experimental and is not required for the exact-key product-alpha contract. The `feature/ma2a-reference-v0.1` branch remains a separate reference implementation and is not treated as a production federation/network dependency.

## Capability matrix

| Capability | Status | Evidence / remaining gap |
|---|---|---|
| Core remember/recall lifecycle | READY | Stable Python facade exists and is covered by the historical test suite. |
| Trajectory known-route resolution | READY | Existing routed memory implementation. O(1) wording must remain limited to justified direct lookup operations. |
| Snapshot persistence | READY FOR ALPHA | Versioned snapshot, CRC32/integrity checks, fsync/atomic replacement and product manifest are exercised through restart/reload tests. Backup/restore lifecycle is still a hardening item. |
| Semantic routing v0.96 | EXPERIMENTAL | Calibrated/adversarial research exists, but it remains outside the product-alpha contract until frozen and independently validated. |
| HTTP `/api/v1` service | READY FOR ALPHA | FastAPI product service exposes health, memory, chat, comparison, administration and application-management endpoints. |
| Organization model/isolation | READY FOR ALPHA | Organization-qualified memory namespaces and isolation tests exist. |
| Administrative API authentication | READY FOR ALPHA | Administrative credential boundary uses constant-time comparison. Production secret management remains deployment responsibility. |
| Application credentials/scopes | READY FOR ALPHA | Organization-local application credentials, per-scope authorization and cross-application isolation are implemented. Plaintext application tokens are returned only once; persistence stores PBKDF2-HMAC-SHA256 verifiers with per-token salts. |
| Memory CRUD/revocation/version HTTP contract | READY FOR ALPHA | Versioned HTTP contract wraps product service without exposing experimental router internals. |
| Provider-neutral LLM adapter | READY FOR ALPHA | Mock, Gemini and OpenAI adapters exist behind the product chat boundary. |
| Live Gemini integration | VALIDATED | Sanitized repository evidence records a successful live `gemini-2.5-flash` call through Memoria.ia with one memory hit and no recorded secret. |
| Live OpenAI integration | VALIDATED | Sanitized repository evidence records a successful live OpenAI call through Memoria.ia with one memory hit and no recorded secret. |
| Context/token/cost instrumentation | READY FOR ALPHA | Per-request memory hits/misses, context size, token counts when supplied, latency, external calls and optional estimated cost inputs are exposed. |
| Baseline vs Memoria comparison | READY FOR ALPHA | `/api/v1/chat/compare` and machine-readable benchmark paths report observed context/token reduction. |
| Web chat/metrics/admin | READY FOR ALPHA | Minimal web UI is served by the same product service and is exercised by automated tests/container smoke tests. |
| Docker / Compose / `.env.example` | READY FOR ALPHA | Reproducible container package, persistent volume and startup configuration exist. CI builds and restarts the container against the same volume. |
| Node identity model | READY FOR ALPHA | Organization/node identity, certificate status/reference, license status and capabilities are represented and exposed without secrets. |
| Customer-controlled local configuration | READY FOR ALPHA | Non-secret configuration and provider credentials are separated. Local alpha secret storage uses mode 0600; external container/environment secret management remains supported and preferred for hardened deployments. |
| MA2A adapter boundary | PARTIAL / SEPARATE | Reference protocol exists separately. Product alpha intentionally does not require federation/network operation. |
| Full MA2A PKI/certificate authority | EXTERNAL MODULE REQUIRED | Trust roots, issuance, revocation and peer-handshake validation belong to MA2A infrastructure rather than the local Memoria.ia alpha. |
| Commercial license metadata | READY FOR ALPHA | Product consumes local entitlement metadata separately from cryptographic identity. Cryptographic issuance/revocation belongs to a future external license authority. |
| Product security review | NOT COMPLETE | Security-sensitive boundaries are tested, but no formal production security review, threat-model sign-off or penetration assessment has been completed. |
| Product benchmark suite | PARTIAL / ACTIVE | Context-reduction and acceptance artifacts exist. Broader latency/scale, crash/fault injection, backup/restore and independent external corpora remain future validation work. |
| Product-alpha CI | PASSING | Dedicated product validation, application-credential and semantic-validation workflows currently pass on the product branch. |

## Architecture mapping

`HTTP/Web -> Authentication/Scope Boundary -> Product Service -> Organization Namespace -> Context Resolver -> Stable ResolutiveMemoryAPI -> Persistence`

Optional LLM flow:

`Product Service -> Context Resolver -> LLMAdapter -> configured provider`

Future network flow:

`Product Service -> MA2AAdapter -> external MA2A implementation`

The LLM adapter receives materialized context. A private trajectory/hash is an internal identifier and is never assumed to be meaningful to an external language model.

## What is already demonstrable end to end

The current product branch can be exercised as a real service rather than only as a Python library:

1. configure an organization and node;
2. start Memoria.ia as a FastAPI service/container;
3. access its web interface;
4. authenticate as administrator or as an application credential with scopes;
5. store and resolve organization-scoped memory;
6. persist state to disk;
7. stop and recreate the container using the same persistent volume;
8. recover the previously stored memory;
9. send a chat request using mock, Gemini or OpenAI provider adapters;
10. inspect memory/context/token/latency/external-call metrics; and
11. compare a baseline context path with the Memoria.ia-selected context path.

The CI product smoke test performs a container restart and validates that state survives across process/container recreation.

## Remaining alpha-close work

The objective is now to close a reproducible **installable product alpha**, not to add more experimental algorithms to its contract.

Priority order:

1. **Documentation synchronization** — keep README/product docs aligned with the product-alpha evidence and clearly separate stable, alpha and experimental claims.
2. **Security baseline** — document threat boundaries and verify secret non-disclosure, authorization isolation, failure behavior and safe defaults. Keep the maturity label `not-security-reviewed` until a formal review occurs.
3. **Backup/restore contract** — add an explicit operator-visible backup/restore procedure and integrity validation without changing the stable core format unnecessarily.
4. **Clean-host deployment evidence** — retain Docker/Compose as the canonical alpha path and document the minimum PC/VPS installation flow.
5. **Acceptance artifact** — require the product-alpha acceptance gate, product benchmark and container restart validation to pass from a clean checkout.
6. **Alpha release metadata** — only after the preceding gates pass, prepare a versioned product-alpha release distinct from the v0.95 research release line.

## Explicitly out of scope for this alpha

The following must not block the first local PC/server product alpha:

- MA2A federation or global network operation;
- full MA2A certificate authority / PKI lifecycle;
- semantic v0.96 promotion to a production default;
- claims of general natural-language understanding;
- claims of general GPU/energy reduction without matched external benchmarks;
- production-grade secret vaulting, multi-region HA or enterprise SSO;
- embedded/ESP32 optimization.

## EXTERNAL MODULE REQUIRED

Module: `ma2a`

Problem: Memoria.ia can hold identity metadata and expose an adapter boundary, but a trusted MA2A root, certificate issuance/revocation, federation trust and network handshake policy are protocol/infrastructure responsibilities.

Required capability: validate an organization/node certificate against an MA2A trust root and return identity/scopes/validity without coupling certificate validity to commercial license entitlement.

Expected interface:

`validate_certificate(certificate_bytes, now) -> {valid, organization_id, node_id, public_key, not_before, not_after, scopes, issuer, reason}`

Acceptance test: valid signed certificate passes; expired, revoked, wrong-root, modified and organization/node-mismatched certificates fail deterministically; license state is not inferred by this function.

Why needed now: it does **not** block the local product alpha. It becomes blocking only when Memoria.ia accepts authenticated MA2A peers or advertises certificate validation/federation as functional.
