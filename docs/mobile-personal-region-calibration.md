# Personal evidence region: calibration gate

The native `personal_evidence` mode is an opt-in, read-only probe. It preserves
the source hierarchy and source ID. It is **not** enabled in OFF.IA's default
response path. A nonempty result returns `CANDIDATES`, `qualified:false` and
the native `UNRESOLVED` status. These records cannot yet establish a fact.

## Private device replay, 25 September 2026

The supplied OFF.IA export had 83 structural observations across 25 conversation
hierarchies. Some legacy observations are tagged `user_assertion` despite being
questions. The raw export is not stored in this repository.

| Cross-conversation probe | Initial native ranking | Gate |
| --- | --- | --- |
| Family subject A | Relevant name record first, but related questions also appear in top results | Fail: unqualified context |
| Family subject B | Name-bearing record first, but a question about subject A also appears | Fail: region contamination |
| Family subject C | A repeated question with an extra word ranks ahead of repeated name records | Fail: question echo |
| Absent technical subject | Unrelated family questions appear | Fail: false HIT |

These failures occur even with assistant output excluded and source provenance
retained. The probe no longer returns `HIT` for them; this is a contract safety
change, not a retrieval fix. A successful 8/8 isolated native diagnostic does
not cover this cross-conversation gate.

The opt-in `probe_structural_regions` preview now groups direct symbol matches
by conversation. It reports the count of exact query-trail echoes separately
from other matching observations, the region's sequence span and its origin ID.
It returns `UNRESOLVED` with `qualified:false` even when candidate regions
exist. An observation with extra symbols is merely *distinct*; it is not
classified as an assertion. The preview does not traverse cognitive
trajectories and performs a scan of observations per region, so runtime cost
and the private replay remain open gates.

## Region preview replay, 26 September 2026

Running the preview against the same 83 private observations, without storing
the export or raw responses in Git, produced these aggregate counts:

| Probe | Activated regions | Observation |
| --- | ---: | --- |
| Family subject A | 21 of 25 | Shared query structure activates many regions |
| Family subject B | 21 of 25 | Exact echoes are separated, but nearby questions remain distinct |
| Absent technical subject | 22 of 25 | Direct overlap alone has unacceptable false activation |

This fails the cross-conversation selection gate. The preview is useful for
inspecting where activation spreads, but its ordering cannot feed a factual
answer. The next gate must compare regional trajectories and confirm that an
absent subject stays unresolved.

## Required before app integration

1. Preserve the whole conversation window as an addressable region, retaining
   observation IDs, order, source kind and origin hierarchy.
2. Activate related regions and distinguish query echoes from new evidence by
   their trajectories and recurrence **within the activated region**. Do not
   infer that the old `user_assertion` label proves assertion.
3. Compare competing regions and expose ambiguity; return unresolved when the
   evidence does not support a specific subject. Do not promote a retrieved
   question or assistant output into a factual answer.
4. Run a synthetic gate for the four rows above, then replay the private export
   locally. Check cold reopen, unrelated queries and runtime cost as the number
   of windows grows. Only then enable a fallback in OFF.IA.

No family words, personal names or language-specific question templates should
be encoded as the retrieval rule. Corpus-wide token frequency and fixed novelty
thresholds were tried against the replay; they improved individual probes but
failed on sparse test histories and reinforced repeated questions. They are not
accepted as the integration gate.
