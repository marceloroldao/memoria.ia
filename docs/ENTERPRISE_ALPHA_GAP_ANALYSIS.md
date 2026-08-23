# Memoria.ia Enterprise — Product Alpha Gap Analysis

Status: pre-alpha planning baseline
Target: PC / VPS / server
Research baseline: `experiment/v0.96-semantic-routing`

## Evidence rule

This document separates demonstrated code from experiments, hypotheses, and missing product capabilities. Experimental benchmark results are not production guarantees.

## Current baseline

The repository already contains a stable Python facade (`ResolutiveMemoryAPI` v0.95), routed lifecycle memory, trajectory-based resolution, snapshot persistence with CRC32 and atomic replace/fsync, a substantial test/experiment corpus, and v0.96 semantic-routing experiments. The `feature/ma2a-reference-v0.1` branch contains a separate MA2A reference implementation with Ed25519 framing, replay guard and namespace policy; it is not treated as a production network implementation.

## Capability matrix

| Capability | Status | Evidence / gap |
|---|---|---|
| Core remember/recall lifecycle | READY | Stable Python facade exists and is tested. |
| Trajectory known-route resolution | READY | Existing routed memory implementation. O(1) claims must be limited to justified lookup operations. |
| Snapshot persistence | PARTIAL | Versioned format, CRC32, fsync and atomic replacement exist; no organization-aware store, backup lifecycle or transactional multi-request service layer yet. |
| Semantic routing v0.96 | EXPERIMENTAL | Active calibrated/adversarial research; preserve outside product contract until frozen and independently validated. |
| HTTP `/api/v1` service | MISSING | Existing API is a Python facade, not a network service. |
| Organization model/isolation | MISSING | No stable organization boundary in persisted memory/API. |
| API authentication | MISSING | No product HTTP auth boundary. |
| Memory CRUD/revocation/metadata HTTP contract | MISSING | Must wrap stable core without exposing experiment internals. |
| Provider-neutral LLM adapter | MISSING | No product adapter boundary or provider implementation. |
| Context/token/cost instrumentation | MISSING | Research benchmarks do not constitute per-request product telemetry. |
| Baseline vs Memoria comparison | MISSING | Must be reproducible and machine-readable. |
| Web chat/metrics/admin | MISSING | No product web UI. |
| Docker / Compose / `.env.example` | MISSING | No reproducible product deployment package. |
| Node identity model | MISSING | Product needs stable node/organization identity records. |
| MA2A adapter boundary | PARTIAL | Reference protocol exists on separate branch; product needs a narrow interface/stub only. |
| Full MA2A PKI/certificate authority | BLOCKED BY EXTERNAL MODULE | Belongs to MA2A infrastructure, not Memoria.ia. |
| Commercial license validation | MISSING | Must remain logically separate from cryptographic identity. |
| Product security review | MISSING | Alpha must not be described as production-secure. |
| Product benchmark suite | MISSING | Need insertion, retrieval, open-set, update/conflict, restart, isolation, latency, LLM outage and context-reduction cases. |

## Architecture mapping

`HTTP/Web -> Product Service -> Organization Boundary -> Context Resolver -> Existing ResolutiveMemoryAPI / optional semantic resolver -> Persistence`

Optional LLM flow:

`Product Service -> Context Resolver -> LLMAdapter -> provider`

Future network flow:

`Product Service -> MA2AAdapter -> external MA2A implementation`

The LLM adapter receives materialized context. A private trajectory/hash is an internal identifier and is never assumed to be meaningful to an external model.

## Prioritized implementation plan

1. **Product domain boundary**: Organization, NodeIdentity, certificate reference/status, license status, application/agent/user scope identifiers. Add isolation tests before HTTP.
2. **Organization-aware memory service**: wrap existing core; one logical memory namespace per organization; CRUD + metadata + persistence contract.
3. **Versioned HTTP API**: `/api/v1/health`, memory CRUD/query/context, organization/node status; authentication boundary and validation.
4. **Deployment**: Docker, persistent volume, `.env.example`, health check, startup docs.
5. **LLM boundary**: provider-neutral `LLMAdapter`; implement one provider only after the interface and metrics contract are tested.
6. **Instrumentation**: hit/miss, bytes/chars/context, token usage supplied by provider, local/LLM latency, external calls, estimated cost with explicit pricing inputs.
7. **Minimal web UI**: chat, per-request metrics, administration/status. Never display secrets.
8. **Product benchmarks**: machine-readable results and baseline-vs-Memoria comparison.
9. **MA2A adapter stub**: import/reference identity metadata only; no federation/network implementation in this repository.
10. **Alpha gate**: restart recovery, organization isolation, automated tests, reproducible benchmark and deploy-from-clean-host instructions.

## Smallest high-value gap selected

Organization isolation is first. It is cross-cutting: API, persistence, authentication, metrics and future MA2A identity all depend on it. The first implementation increment therefore introduces product identity/domain types and tests without modifying the experimental memory algorithms.

## EXTERNAL MODULE REQUIRED

Module: `ma2a`

Problem: Memoria.ia can hold identity metadata and expose an adapter boundary, but a trusted MA2A root, certificate issuance/revocation, federation trust and network handshake policy are protocol/infrastructure responsibilities.

Required capability: validate an organization/node certificate against an MA2A trust root and return identity/scopes/validity without coupling certificate validity to commercial license entitlement.

Expected interface: `validate_certificate(certificate_bytes, now) -> {valid, organization_id, node_id, public_key, not_before, not_after, scopes, issuer, reason}`.

Acceptance test: valid signed certificate passes; expired, revoked, wrong-root, modified and organization/node-mismatched certificates fail deterministically; license state is not inferred by this function.

Why needed now: not blocking local product alpha. It becomes blocking only when Memoria.ia accepts authenticated MA2A peers or advertises certificate validation as functional.
