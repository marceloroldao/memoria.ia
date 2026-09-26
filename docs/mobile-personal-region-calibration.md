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
trajectories. It now scans observations once and locates each conversation in
an ordered region index; token comparison and the private replay remain open
gates. This changes traversal cost, not the activation or evidence criteria.

The preview additionally reports `embedded_query_count`: observations whose
ordered symbol trail contains the whole query trail as a proper contiguous
span. The trail recurrence probe exposes `contains_query_trail` on each
distinct full payload. Thus an exact repeated question and a new narrative
containing the same question remain separate observations. This is a read-only
structural diagnostic; it does **not** infer that the narrative supports an
answer, create a persistent phrase node, or reinforce any field on lookup.
Case and punctuation follow the native tokenizer; paraphrases and inserted
words inside the query span do not count as exact containment.
The trail result separately reports `query_echo_occurrences`,
`embedded_occurrences` and `embedded_payload_count` over the complete probe,
before pagination. Two copies of the same containing payload in different
conversation regions count as two occurrences but only one distinct containing
payload. These counts describe structure, not independent factual support.
When the exact query trail was itself observed from a user source, a distinct
containing trail now exposes a read-only `composition`: the observed base's
fingerprint, its first starting position, its length, the remaining suffix
length and the number of positions containing it. For example, a new request
can be represented as three prefix symbols plus the already observed five
symbol question trail. The fingerprint identifies the full symbol trail used
by this probe; it is not a persisted nodule or a claim of semantic equivalence.
Without an observed base the `composition` is null even if the query text is
contained. Exact echoes also have null composition. Raw occurrences remain
stored separately. The private replay checks base-address links across cold
reopen and emits aggregate counts only.
In the 83-observation replay, the four private probes yielded 1, 0, 0 and 0
distinct compositions, respectively. The first had a prefix and no suffix;
all 64 displayed witnesses remained addressable. The absent technical probe
had neither an observed base nor a composition. This validates the structural
address link in this sample, not factual selection or compression. The
decomposition compares the current corpus and does not establish whether the
base was observed before the containing payload.

The native observation runtime now indexes distinct normalized symbol trails
**within each conversation field**. A second source with the same trail is
persisted as another raw occurrence but does not advance that field's tick,
within-trail weights or temporal recent set. This also holds across case and
punctuation differences under the native tokenizer; an identical source ID
and sequence remains an idempotent duplicate and creates no second raw record.
`observe_structural_text` reports `duplicate` for that source identity,
`new_trail` for a field update and `distinct_trail_count` for the conversation.

A different payload containing a previously observed complete symbol trail
remains a new field observation. The longest contained trail is treated as a
reused nodule. Its internal within-trail links receive **zero** additional
weight; new links from/to the surrounding symbols receive the existing
`1 / token_distance` contribution. Temporal links to an earlier trail skip
the reused span on both sides when it also appears there; the surrounding
context can still form temporal associations. A repeat of the
whole normalized trail does not advance the field clock or add any edge.
Occurrences are kept for provenance, never converted into factual strength.

BDR structural-text schema 2 stores the first raw occurrence inline. An exact
byte copy stores source metadata plus a reference to that earlier occurrence.
A new text with a **byte-identical and token-aligned** contained payload stores
its prefix, earlier occurrence reference and suffix. The longest available
payload wins; a later composition can itself be referenced. Reconstruction
reads earlier occurrences in order, preserving exact UTF-8 text, source IDs,
source kinds and sequences across a cold reopen. References can cross
conversation fields within the same organization. Existing schema 1 inline
rows remain readable and acquire references on later writes without rewriting
history. A case or punctuation variation that shares normalized symbols but
does not contain the prior raw bytes still stores its own surface text inline;
the field still recognizes the normalized nodule and avoids internal weight.
The current implementation chooses one longest reused span per new trail and
does not yet optimize the duplicate text reconstructed in process memory.
These are structural storage and association weights, not factual confidence.

On the private export, 83 raw observations across 25 conversations yielded
75 distinct region trails:
8 repeat occurrences did not update their local field. The four cross-region
probes still returned `UNRESOLVED`, and all 64 displayed witnesses resolved
after cold reopen. The clock now counts distinct structural trails, not raw
events; elapsed-time forgetting needs its own later policy.
The host Python adapter gate exposed the expected ranking change: in a local
synthetic history, a repeated cat-name record no longer outranks an unrelated
cat observation merely because it was copied twice. Both raw sources and the
other observation remain addressable before and after restart, but the legacy
default local resolver may still label this ambiguous candidate list `HIT`.
That label is not a qualified personal fact; the local selection ambiguity is
an open integration gate alongside the cross-conversation failures. The
adapter test now checks provenance and recurrence without requiring the old
duplicate-driven first position.

The region preview now exposes `max_ordered_span`: the longest contiguous
symbol path shared by the query and any **distinct** observation in a region.
Exact query echoes do not contribute. This preserves order without a vocabulary
of question templates; it still measures a text path, not a cognitive or
factual trajectory, and does not change ranking or qualification.
Each region also returns one `witness` with the source ID, source kind, order
and ordered-span length of the distinct observation supporting that maximum.
An echo-only region has `witness:null`. Ties use the earliest sequence and
then source ID, so the addressable window read can inspect the same occurrence
after cold reopen. The legacy source kind is provenance, not proof of assertion.
The local private replay checked each non-null witness in the first 16 regions
of four probes against the addressable raw window: 64/64 source IDs and
sequence numbers resolved. No raw witness or personal text is committed.

In a local replay of the same private 83-observation export, one repeatedly
asked family query activated 23/25 regions. Among the first 16 returned, 14
had an ordered span of at most two symbols, while two reached four or five.
An absent technical question activated 22/25 regions; the first 16 had spans
of one (13 regions) or two (3 regions), with no exact echo or containing
payload. The preview limit means these distributions cover the first 16
regions only. Near-question variants can also have a long ordered span, so
none of these counts qualifies an answer or supplies a selection threshold.
The raw export and responses remain outside Git.

The replay can be repeated with `scripts/mobile_region_replay.py` using a local
OFF.IA JSON export, a private JSON array of query strings, and the built native
shared library. It opens a temporary BDR database, replays observations,
flushes and reopens it, checks the read-only probes, and resolves every
displayed witness through its raw window. Standard output contains only case
indices and aggregate counts; the input files stay local. This gate verifies
provenance and the unqualified response contract. It does not decide whether
a returned region answers a question.

An exploratory branch contrast used symbols that differed between nearby
observed question trails. On four private probes it reduced raw activation
from 23, 21, 19 and 22 regions to 17, 4, 12 and 0, respectively. The absent
control improved, but two personal probes still spread across many regions.
This contrast is **not** a retrieval rule, factual gate, or native code path.

## Region preview replay, 26 September 2026

Running the preview against the same 83 private observations, without storing
the export or raw responses in Git, produced these aggregate counts:

| Probe | Activated regions | Unseen query symbols | Observation |
| --- | ---: | ---: | --- |
| Family subject A | 21 of 25 | 0 | Shared query structure activates many regions |
| Family subject B | 21 of 25 | 0 | Exact echoes are separated, but nearby questions remain distinct |
| Absent technical subject | 22 of 25 | 3 | Direct overlap alone has unacceptable false activation |

This fails the cross-conversation selection gate. The preview is useful for
inspecting where activation spreads, but its ordering cannot feed a factual
answer. The next gate must compare regional trajectories and confirm that an
absent subject stays unresolved.
The count of unseen query symbols is a diagnostic signal, not a rule that
missing symbols always imply an absent fact; paraphrases can contain new words.

An exploratory contrastive score combined query-symbol co-occurrence within
an observation, recurrence across regions and distance from a repeated query
within its conversation. In the private replay, the expected region for family
subject A ranked first, and the three regions carrying observations for family
subject B ranked in the first three positions. The absent technical subject
still gave a high score to an unrelated region. This score is **not** part of
the native selection or answer contract. A new synthetic negative test also
records that a question with one extra word is a distinct trail, while it
remains unqualified evidence.

A separate read-only trail recurrence probe groups identical observed symbol
sequences and reports `occurrences` and `region_count` independently. The gate
checks two repeats in one conversation plus one in another as three occurrences
from two regions. A different continuation remains a separate trail, and an
exact repeated question is marked `query_echo`. Assistant-generated text is
excluded. These are structural observations, not corroborated facts or an
automatic conflict decision; the probe still returns `UNRESOLVED`.
Each group now includes the first 16 source references with conversation ID,
source ID and sequence, plus `sources_truncated`. The addressable window read
can inspect the full raw region when a group has more occurrences.
The trail probe also records the deepest shared token prefix where two distinct
trails have different next symbols. `branch_address` fingerprints that prefix,
`branch_depth` counts its symbols, and `divergent_trail_count` counts other
trails diverging there. An exact prefix extension is not a fork. Two alternative
continuations can thus point to the same compositional address without being
declared a contradiction or a fact. This diagnostic currently compares every
pair of distinct trails, so its quadratic group cost remains a runtime gate.

The private replay illustrates why region count cannot equal corroboration:
the exact repeated question for family subject C occurred 12 times in 10
conversation regions. Exact query echoes for subjects A and B appeared 3 times
in 2 regions and 7 times in 4 regions, respectively. The absent technical
query had no exact echo. These aggregate counts are not entered as factual
support; repeated questioning can span independent conversation IDs.

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

## Functional proof gate, 26 September 2026

`scripts/mobile_personal_proof_gate.py` exercises the built native library with
22 invented observations. It checks positive retrieval, a different subject,
an absent recombination whose individual words all occur elsewhere, repeated
questions, a near question, two competing name records, assistant-output
exclusion, exact source addresses and cold BDR reopen. The `--strict` mode
returns failure until **all** functional gates pass; it is intentionally not
an app acceptance gate or a factual fallback.

| Test | Current observation | Result |
| --- | --- | --- |
| Known name | Answer source addressable, but the near question ranks first | Fail |
| Other subject | Its answer source is present, but an earlier question ranks first | Fail |
| Absent recombination | Eight unrelated/question candidates, led by a different subject's power record | Fail |
| Assistant text | Generated output excluded from the personal candidates | Pass |
| Competing sources | Both conflicting user sources remain visible and unqualified | Pass |
| Cold reopen | Candidates and exact source addresses survive | Pass |

Eight of eleven script checks pass; the three failures concern selection and
absence. Merely returning `UNRESOLVED` alongside irrelevant `CANDIDATES` is
not proof that the system has recognized the missing answer. The old local
resolver's `HIT` and the opt-in personal probe remain separate contracts.

The same script also inspects an occurrence-local continuation path through
the native trail and window APIs. It anchors on an observed exact query trail
and reads only the immediate next observation in **that same conversation**;
it never jumps through a shared symbol into another conversation or skips an
assistant turn. Two independent synthetic conversations continue with the
same text, one continues with a competing text, and another repeats the
question. An assistant turn blocks traversal even when a user turn follows
it. All four user continuations remain addressable after cold reopen. An
absent query with no observed echo has zero such continuations.
These are observed transitions, **not verified answers**: an immediate next
user turn may itself be another question. The path is a research diagnostic,
not a selector or a weight rule.

In a local private replay, the four most frequent exact surface texts occurred
6, 5, 4 and 3 times. Their immediate user-successor counts were 6, 3, 4 and
2, respectively, across 6, 2, 2 and 2 conversation regions. These counts do
not classify the successor texts or qualify a fact. No private text, source ID
or raw response is stored in Git. Further work should compare the competing
regional trajectories and test whether a candidate survives absent-subject
and near-question controls before changing OFF.IA or optimizing throughput.
