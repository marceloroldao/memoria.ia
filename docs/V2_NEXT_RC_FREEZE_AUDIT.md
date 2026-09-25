# Memoria.ia V2 — Next RC Freeze Readiness Audit

Status: **BDR RC4 PUBLISHED; MEMORIA.IA CROSS-REPOSITORY REGRESSION PENDING**

## 2026-09-25 dependency resolution

BDR `v1.2.0-rc4` is published as a GitHub pre-release at
`317882a00f041fc1568ff986af8016b09453f21a`. Its tag points to that
commit. BDR CI run 36062508821 and the RC4-specific validation run
36062508908 passed on that exact commit. Resolutive-DB issue #39 is closed.
The current Memoria.ia Docker/native/mobile workflows now pin that commit.

The checklist and blocker analysis below record the state at the original
post-R14 audit; the external publication condition is now satisfied. The next
Memoria.ia freeze still requires native, Android, product/server and cognitive
regressions against the published RC4 pin. GitHub publication does not imply a
Zenodo DOI for this BDR candidate.

Audit baseline (post-R14 main):

- Memoria.ia commit: `e5fe858b2a2bef0d07286ee855538cace112eed3`
- Previous immutable publication: `v2.0.0-rc1`
- Previous archived DOI: `10.5281/zenodo.22908785`
- Previous functional freeze remains untouched: `bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9`

This audit is for the **next cognitive-core release candidate**. It does not
retroactively change RC1 and it does not claim that OFF.IA natural-language
interpretation is already complete.

## Post-RC1 reconciliation status

The R1-R14 line is now integrated on main.

| Gate | Status | Evidence / boundary |
| --- | --- | --- |
| Structural trajectory substrate | PASS | occurrence-local opaque-address trajectories |
| Durable trajectory + evolving address state | PASS | cold-reopen/replay gates |
| Hierarchical/multiscale composition | PASS | false-consensus protections retained |
| Branch / rollout / recovery | PASS | no global-address cross-occurrence stitching |
| Structural attractor competition | PASS | competing evidence remains visible |
| Structural equivalence | PASS WITH LIMIT | witnessed/revocable equivalence only; no unseen lexical paraphrase claim |
| Temporal current/previous/history/change | PASS | explicit address-state operations, zero LLM |
| Unified resolutive inference | PASS | resolved/ambiguous/terminal/unresolved result surface |
| Decisive no-LLM benchmark | PASS | recurrence, distractors, negatives, traversal, cold reopen, query immutability |
| Context Compiler v2 | PASS | structured cognitive packet; not a universal byte compressor |
| Epistemic response boundary | PASS | model/external claim remains candidate, not truth |
| Explicit learning admission | PASS | accept + evidence required; competing evidence preserved |
| Cognitive ABI v2 | PASS | local/server/model origin planes and deterministic JSON envelope |
| bit.analyze convergence | PASS WITH LIMIT | StructuralEvent and RealitySlice converge at trajectory layer; exact intra-slice timing not yet used by attractor |
| Progressive LLM reduction benchmark | PASS | 5/5 controlled cognitive cases complete pre-language with 0 LLM/external calls |

Latest R14 PR gate: PR #359 completed the five required workflows successfully
before merge. The measured positive and negative results are recorded in
`docs/V2_POST_RC1_RECONCILIATION.md`.

## Freeze-policy checklist

- [x] RC1 tag/DOI/freeze remains immutable.
- [x] trajectory persistence survives cold reopen.
- [x] no cross-occurrence stitching is gated.
- [x] hierarchical/multiscale false-consensus protections are present.
- [x] attractor competition is reproducible.
- [x] current/previous/change works without LLM.
- [x] inference queries are read-only / immutable.
- [x] negative structural cases remain unresolved.
- [x] historical capabilities are classified as RECOVER / ADAPT / TEST-ONLY /
      ABSORBED / DEFER / DROP.
- [x] limitations and negative results are recorded.
- [ ] next candidate names an immutable **published/frozen BDR artifact that
      actually contains every BDR API symbol required by the runtime**.

The unchecked BDR item is a release blocker.

## BDR provenance blocker

The published BDR `v1.2.0-rc1` artifact is frozen at:

- commit `eb77ad7286f234243ca1ed1a2af2d55df8c12238`
- DOI `10.5281/zenodo.22784729`

That published header does **not** expose `bdr_atomic_c_clear()`.

The current Memoria.ia native runtime calls `bdr_atomic_c_clear()` through
`memoria_persistence_reset()`. Current build/workflow metadata pins:

- `d09914b85646353d8fd004ccf99e96a94fab9eef`

That BDR commit is newer than the published RC1 artifact and merged durable atomic
logical clear on 2026-09-21. Therefore `d09914...` must not be described as
`v1.2.0-rc1`, and current Memoria.ia cannot honestly claim build compatibility
with the published RC1 API surface.

Cross-repository release dependency is tracked in Resolutive-DB issue #39:
**Freeze a published BDR candidate that includes atomic logical clear**.

Freeze can proceed after one of these is demonstrated and documented:

1. preferred: a new immutable/published BDR candidate includes the required logical
   clear API and passes its durability/restart/platform gates; Memoria.ia pins that
   exact candidate commit/tag;
2. alternative: Memoria.ia removes the hard dependency on the additive clear symbol
   and proves compatibility against published BDR `v1.2.0-rc1`.

Do not silently substitute BDR main for a published candidate.

## Historical PR disposition before freeze

- PR #351 — **CLOSED / SUPERSEDED** by merged R9 PR #352.
- PR #355 — **CLOSED / SUPERSEDED** by merged R11 admission PR #356.
- PR #320 — **ABSORBED** at the structural-observation pipeline level. Its exact
  historical HTTP transport is not the cognitive authority.
- PR #317 — **TEST-ONLY / KEEP OPEN FOR INTEGRATION WORK**. Preserve its real
  no-external-call E2E acceptance goal, but do not merge its stopword/lexical
  fallback policy.
- PR #310 — **HISTORICAL BDR VALIDATION / DO NOT MERGE WHOLESALE**. Its shared-handle
  and cold-reopen lessons have been absorbed, but the current release dependency
  must now be resolved through an immutable BDR candidate rather than this diverged
  branch.
- PR #296 / #297 — **HISTORICAL EXPERIMENT / CI-ONLY LINE**. Mechanisms and tests
  were reconciled through R1-R14; do not merge the diverged branches wholesale.

## Scope boundary for the next freeze

A next cognitive-core RC may claim:

- structural and temporal inference before language generation;
- explicit conflict/uncertainty/provenance;
- append-only epistemic admission;
- versioned local/server cognitive ABI;
- modality-neutral bit.analyze structural convergence at trajectory level;
- measured zero-LLM completion for the controlled R14 structural/temporal cases.

It must **not** claim yet:

- general natural-language understanding without an interpretation layer;
- general lexical paraphrase;
- full RAG superiority;
- universal context/token compression;
- exact multimodal temporal association in the R8 attractor;
- complete OFF.IA natural-language E2E integration.

## Next action

Resolve Resolutive-DB issue #39, pin the resulting immutable BDR candidate, run the
full Memoria.ia native/mobile/product/cognitive regression matrix against that exact
pin, then create the freeze commit. Only after that should release metadata,
tag/DOI and publication commits be prepared.
