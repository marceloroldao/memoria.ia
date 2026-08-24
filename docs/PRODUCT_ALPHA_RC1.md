# Memoria.ia Product Alpha RC1

Candidate tag: `v0.99.0-alpha.1`
Python package version: `0.99.0a1`
Status: release candidate for the first installable PC/server Product Alpha. Not production-ready.

## Scope frozen for RC1

RC1 contains the validated v0.95 research lineage plus the product layer developed on `product/enterprise-alpha`:

- organization and node identity boundary;
- organization/application scoped memory access;
- append-only logical versions and revocation;
- persistent snapshot and restart recovery;
- FastAPI `/api/v1` service;
- administrator authentication;
- scoped application credentials with verifier-only persistence;
- Docker and Docker Compose deployment;
- minimal web UI;
- provider-neutral chat adapter;
- OpenAI and Gemini adapters;
- observed token/context/latency/external-call metrics;
- baseline-vs-Memoria comparison;
- validated product-state backup/restore;
- operator runbook;
- negative security/failure-path tests;
- machine-readable acceptance artifact.

## Explicitly outside RC1

The following are not release blockers for this candidate and must not be represented as production capabilities:

- semantic routing v0.96 as a stable API contract;
- MA2A federation or production PKI;
- external license authority enforcement;
- production security certification;
- SSO/OIDC/SAML;
- built-in TLS termination;
- encrypted storage at rest;
- multi-region/high-availability operation;
- claims that Memoria.ia replaces a general-purpose LLM.

## Release gates

A commit may be tagged as `v0.99.0-alpha.1` only when all of the following are true on the exact candidate SHA:

1. `product-alpha validation` is green;
2. `product application credentials` is green;
3. `v0.96 semantic validation` remains green so experimental work has not regressed;
4. full pytest regression is green;
5. container build succeeds;
6. HTTP/UI smoke test succeeds;
7. persistent restart recovery succeeds;
8. operator backup/validate/clean-restore succeeds;
9. alpha security negative gate succeeds;
10. product acceptance artifact reports PASS;
11. branch is not behind `main`;
12. PR #9 remains mergeable;
13. `security_status` remains `not-security-reviewed`.

## Versioning rule

`v0.99.0-alpha.1` is intentionally distinct from the archived v0.95 research release and from the experimental v0.96 semantic-routing line. The `0.99` line means "pre-v1 product integration"; it does not imply production readiness.

Python packaging uses PEP 440 form `0.99.0a1`; the human/Git tag form is `v0.99.0-alpha.1`.

## Candidate release title

`Memoria.ia v0.99.0-alpha.1 — First PC/Server Product Alpha`

## Candidate release summary

This is the first installable Memoria.ia product candidate built around the existing Resolutive Memory research core. It provides a local PC/server API and web interface, scoped organizations/applications, persistent memory, OpenAI/Gemini integration, measurable context reduction, Docker deployment, restart recovery, and validated backup/restore.

The release remains an alpha. Security controls have automated negative-path coverage, but the product has not undergone an independent production security review. Semantic routing v0.96 and MA2A federation remain experimental/separate from the stable product-alpha contract.
