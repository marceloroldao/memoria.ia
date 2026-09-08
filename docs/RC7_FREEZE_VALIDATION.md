# RC7 Cumulative Freeze Validation

Status: freeze candidate

RC7 scope is stabilization only. No new runtime capability is part of this candidate.

## Functional freeze point

Last RC7 runtime correction commit lineage:

`3f72f7e46c976245818e8878e36f6d906d6ba0ba`

Subsequent RC7 work is restricted to regression tests, validation, documentation, packaging, and release metadata unless a release-blocking defect is discovered.

## Stabilization phases

### Phase A — semantic path regression matrix

Validated direct-resolution precedence, bounded semantic activation, deterministic context construction, duplicate-evidence handling, and internal-only `semantic_role` metadata.

Result: no runtime correction required.

### Phase B — provenance and contamination barriers

Validated that `assistant_generated` evidence cannot outrank factual user evidence, cross-namespace validation fails closed, generated echoes cannot replace factual roots, invalidated roots invalidate derived lineage, and external imports retain factual provenance.

Result: no runtime correction required.

### Phase C — runtime/server boundary parity

Validated that semantic activation wraps chat only, public `/conversation/*` routes retain the original conversation service, runtime selection fails closed, storage health reports the active boundary, and shared native storage is only selected when both conversation and episodic runtimes are native.

Result: no runtime correction required.

### Phase D — context budget and ranking boundaries

Validated exact confidence thresholds, hop decay, atomic context-line budgeting, deterministic ranking under insertion-order variation, oversized-edge skipping, and fail-closed empty concepts.

Result: one existing runtime defect discovered and corrected. Floating-point representation could cause a mathematically exact confidence boundary (`0.625 × 0.72 = 0.45`) to be rejected. The comparison was stabilized with a narrow tolerance while preserving the configured threshold semantics.

### Phase E — persistence and performance

Validated repeated SQLite restart equivalence, durable-backend preference, non-amplifying repeated semantic activation, and deterministic read-only activation behavior. Existing conditional native-BDR persistence coverage remains active when the native extension is available. Layered performance remained green.

Result: no additional runtime correction required.

## Release-blocking gates

The cumulative RC7 freeze must remain green on:

1. v0.96 semantic validation;
2. product-alpha validation;
3. product application credentials;
4. Android mobile ABI where triggered/applicable;
5. layered performance baseline;
6. Automatic Context when runtime-changing paths trigger it;
7. release metadata validation.

## RC6 archival consistency prerequisite

Before RC7 publication, the repository must consistently retain the RC6 archival lineage:

- RC6 DOI: `10.5281/zenodo.22648409`;
- RC5 DOI: `10.5281/zenodo.22439650`;
- RC6 public tag: `v1.0.0-rc6`;
- RC6 tag target remains `05a537b1534750ec9856cb5f5f6cdc268b5db5f9`;
- RC6 functional freeze remains `bcef1111f17be06d8f4c26e78bce4a55cf8e1fbd`.

The GitHub release body was published before the RC6 DOI existed and may still contain the pre-DOI sentence. It must be updated independently if release-edit write access is available; the immutable release/tag lineage must not be rewritten to solve this metadata-only inconsistency.

## Freeze decision rule

RC7 may be declared functionally frozen when all currently triggered cumulative gates are green and no release-blocking regression remains. Any new capability, including automatic semantic-role learning, new public/external learning inputs, or ontology expansion, remains post-RC7 work.
