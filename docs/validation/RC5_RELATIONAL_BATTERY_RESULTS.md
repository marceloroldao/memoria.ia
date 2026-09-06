# RC5 Relational Memory Validation Battery — Cumulative Results

Target: `v1.0.0-rc5`

Functional freeze commit: `06c747478e05ee11ab2c5c3c24cf75365262b872`

Release preparation commit: `1efced0caceb00ce16cebcdd98338631d254182d`

Validation branch: `test/rc5-relational-battery`

Policy: positive and negative results are cumulative. Historical failures are retained after correction; a later PASS does not erase the original failure.

## Executive status

| Phase | Scope | Status | Evidence / pending item |
|---|---|---|---|
| A | Native deterministic relational core + portability | PASS / CROSS-PLATFORM GREEN | Historical Windows harness and UTF-8 failures corrected and retained below |
| B | Directional type collection / taxonomy | PASS / CROSS-PLATFORM GREEN | RC5-B07..B12 |
| C | Resolver precedence contract | PASS / CROSS-PLATFORM GREEN | RC5-B13..B16 |
| D | Namespace + supersession adversarial matrix | PASS / CROSS-PLATFORM GREEN | run `34034750890`, RC5-B17..B22 |
| E | Persistence / restart consistency | PASS / CROSS-PLATFORM GREEN | run `34038779945`, RC5-B23..B27 |
| F | Scale / performance probe | PASS FUNCTIONALLY / CROSS-PLATFORM GREEN | run `34039160121`, RC5-B28..B31; absolute latency numbers still pending a benchmark-mode run with uncaptured output |
| G | Mixed conversational adversarial corpus | PASS / CROSS-PLATFORM GREEN | run `34039590580`, RC5-G01..G06 |

Current release-validation conclusion: no known functional blocker remains in Phases B-G. The only open item in this battery is performance characterization: Phase F proved correctness/no-runaway through 50,000 relations, but the shared CI run did not expose the per-scale latency prints, so no absolute latency claim is recorded.

## Historical failures and corrections

### Run 34006309839 — Windows executable-suffix harness failure

- Ubuntu: PASS.
- Windows: FAIL — `622 passed, 28 skipped, 9 errors, 2 warnings`.
- All 9 errors occurred during setup of `tests/test_native_python_concept_rewrite_parity.py`.
- Root cause: C compilation succeeded, but the fixture expected an output path without the Windows `.exe` suffix, so `output.is_file()` failed.
- Classification: test-harness portability defect; no semantic mismatch was demonstrated by those 9 errors.
- Correction: make the native test binary path platform-aware.
- Historical negative result retained.

### Run 34033799428 — remaining Windows UTF-8 parity failure

- Ubuntu: PASS.
- Windows: FAIL — `630 passed, 28 skipped, 1 failed, 2 warnings`.
- The `.exe` defect was fixed; 8 of 9 native/Python rewrite parity cases passed.
- Remaining case: `qual a diferença de potencial do charger`.
- Python reference: `REWRITTEN`; native Windows CLI: `UNCHANGED`.
- Root cause: Windows narrow `argv` converted the UTF-8 query through the active code page before the native kernel received it.
- Correction: send the query to the native CLI through UTF-8 `stdin` rather than narrow `argv`.
- Historical negative result retained.

### Run 34034430288 — UTF-8 correction validated

- Ubuntu: PASS.
- Windows: PASS.
- The Portuguese `diferença de potencial` case preserves native/Python parity.
- The correction changed only the test/input boundary; the Portuguese test was not weakened or converted to ASCII.

## Phase B — Directional type collection / taxonomy matrix

Status: PASS / CROSS-PLATFORM GREEN

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B07 | Type collection | Alt and Luna are gatos; Rex is cachorro | gato collection returns only Alt and Luna | PASS |
| RC5-B08 | Taxonomy direction | gato is animal | animal collection returns direct member gato, not transitive Alt/Luna | PASS |
| RC5-B09 | Parallel type isolation | Rex is cachorro while cats and taxonomy coexist | cachorro collection returns only Rex | PASS |
| RC5-B10 | Namespace isolation | Nina is gato only in session-b | session-b gato collection returns Nina only | PASS |
| RC5-B11 | Supersession | Milo→gato evidence is superseded | Milo excluded from active gato collection | PASS |
| RC5-B12 | Attribute contamination | gato has pelos | pelos relation never appears as gato membership | PASS |

Conclusion: collection remains directional and type-clean. Taxonomy, attributes, superseded evidence and foreign namespaces do not silently become collection members.

## Phase C — Resolver precedence contract

Status: PASS / CROSS-PLATFORM GREEN

Frozen precedence: `direct/base HIT → relation → collection → neighborhood → UNRESOLVED`.

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B13 | Direct precedence | Base resolver returns anything except UNRESOLVED | return immediately; relational modes cannot override it | PASS |
| RC5-B14 | Relation vs collection | Base misses and relation can resolve | relation evaluated before collection | PASS |
| RC5-B15 | Collection vs neighborhood | Relation misses | collection evaluated before one-hop neighborhood | PASS |
| RC5-B16 | Final fallback | No mode resolves | remain UNRESOLVED | PASS |

`tests/test_rc5_resolver_precedence_contract.py` freezes this ordering against accidental future reordering.

## Phase D — Namespace and supersession adversarial matrix

Status: PASS / CROSS-PLATFORM GREEN — run `34034750890`

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B17 | Namespace contradiction | `charger→34v` in session-a and `charger→99v` in session-b | session-a never resolves 99v | PASS |
| RC5-B18 | Superseded dominance | superseded `charger→danger` confidence 1.00; active `charger→safe` 0.90 | danger excluded; safe resolves | PASS |
| RC5-B19 | Duplicate active evidence | same `charger→34v` edge at 0.95 and 0.82 | active paths retained/ranked by confidence | PASS |
| RC5-B20 | Cross-namespace false path | session-b has `charger→99v→danger` | never leaks into session-a | PASS |
| RC5-B21 | Superseded foreign value | session-b superseded `charger→120v` at 1.00 | remains UNRESOLVED | PASS |
| RC5-B22 | Empty namespace isolation | empty namespace has `charger→12v` | only empty namespace resolves 12v | PASS |

Dedicated native matrix: `native/mobile/tests/rc5_namespace_supersession_matrix.c`.
Cross-platform wrapper: `tests/test_rc5_namespace_supersession_matrix.py`.

Conclusion: confidence does not override namespace boundaries or supersession state. A high-confidence stale/foreign edge remains excluded.

## Phase E — Persistence / restart consistency

Status: PASS / CROSS-PLATFORM GREEN — run `34038779945`

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B23 | Durable sync | active + superseded lineage state written/synced | sync succeeds before shutdown | PASS |
| RC5-B24 | Close/reopen | reopen same data path and organization | persisted state opens successfully | PASS |
| RC5-B25 | Supersession after restart | derived memory invalidated before shutdown | remains inactive after reopen | PASS |
| RC5-B26 | Active correction after restart | replacement `b-new` active before shutdown | remains active after reopen | PASS |
| RC5-B27 | Build integration | native lineage restart executable remains wired into test build | restart regression cannot silently disappear | PASS |

Runtime evidence in `native/mobile/tests/lineage_state.c` executes save → sync → close → reopen → resolve. `tests/test_rc5_persistence_restart_contract.py` freezes these invariants in the standard regression.

Conclusion: restart does not resurrect superseded state or discard the active correction in the tested lineage path.

## Phase F — Scale / performance probe

Status: PASS FUNCTIONALLY / CROSS-PLATFORM GREEN — run `34039160121`

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B28 | 100 edges | bounded 4-hop traversal in 100-edge chain | correct path preserved | PASS |
| RC5-B29 | 1,000 edges | bounded 4-hop traversal in 1,000-edge chain | correct path preserved | PASS |
| RC5-B30 | 10,000 edges | bounded 4-hop traversal in 10,000-edge chain | correct path preserved | PASS |
| RC5-B31 | 50,000 edges | bounded 4-hop traversal in 50,000-edge chain | correct path preserved; no runaway | PASS |

Native probe: `native/mobile/tests/rc5_relation_scale.c`.
Cross-platform wrapper: `tests/test_rc5_relation_scale.py`.

Observed regression result: Ubuntu completed with `635 passed, 28 skipped, 5 warnings in 32.44s`; Windows also completed successfully. This is the whole-suite duration, not a relation-resolver latency measurement.

Pending characterization: the scale probe emits per-size timing, but `pytest -q` captured those prints in this green CI run. Therefore the battery records functional PASS through 50,000 relations but intentionally makes no absolute latency/throughput claim. A dedicated benchmark-mode run with uncaptured timing output remains optional before/after RC5 freeze.

## Phase G — Mixed conversational adversarial corpus

Status: PASS / CROSS-PLATFORM GREEN — run `34039590580`

Corpus combines animals, vehicles, colors, ownership, taxonomy, corrections, foreign namespaces, superseded facts, ambiguous concepts and weak noise in the same memory set.

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-G01 | Namespace/color contamination | Alt is preto in session-a; foreign session-b says verde at confidence 1.00 | preto resolves; verde does not leak | PASS |
| RC5-G02 | Conversational correction | old Jetta→preto turn superseded; correction Jetta→vermelho active | vermelho resolves; preto is UNRESOLVED | PASS |
| RC5-G03 | Mixed taxonomy | Alt→gato→animal amid unrelated vehicle/person facts | 2-hop taxonomy path resolves | PASS |
| RC5-G04 | Ownership direction | Marcelo→Alt ownership | forward resolves; Alt→Marcelo does not | PASS |
| RC5-G05 | Mixed type collections | gatos and veículos coexist with colors, taxonomy and foreign Rex | gatos={Alt,Luna}; veículos={Kombi,Jetta,Corsa}; no contamination | PASS |
| RC5-G06 | Weak-noise rejection | Alt similar_to Jetta at confidence 0.30 with threshold 0.80 | false Alt→Jetta relation remains UNRESOLVED | PASS |

Native corpus: `native/mobile/tests/rc5_conversational_corpus.c`.
Cross-platform wrapper: `tests/test_rc5_conversational_corpus.py`.

CI run `34039590580` completed successfully on both `ubuntu-latest` and `windows-latest`.

Conclusion: the deterministic relational core remains fail-closed under a mixed, more realistic corpus. Corrections, namespace boundaries, directionality, collection purity and confidence thresholds remain effective when several semantic domains coexist.

## Consolidated RC5 assessment

### Positive findings

- Directional multi-hop traversal remains bounded and cycle-safe.
- Type collection is not confused with taxonomy or attributes.
- Resolver precedence is explicitly frozen and regression-tested.
- Namespace isolation survives adversarial conflicting facts.
- Superseded high-confidence evidence cannot defeat an active correction.
- Persistence/restart preserves active/superseded lineage state in the tested path.
- Functional traversal remains correct at 100, 1,000, 10,000 and 50,000 relation probes.
- Mixed conversational data does not create the tested cross-domain false positives.
- Portuguese UTF-8 parity is green on Windows after correcting the input boundary.

### Negative findings retained

1. Windows `.exe` test-harness portability defect — discovered in run `34006309839`, corrected.
2. Windows narrow-`argv` UTF-8 defect affecting `diferença de potencial` — discovered in run `34033799428`, corrected and validated in run `34034430288`.
3. Phase F CI output limitation — per-scale latency values were captured by pytest, so performance numbers cannot be claimed from run `34039160121`. This is a characterization/documentation limitation, not a functional failure.

### Remaining pendency

- No functional pendency remains in Phases B-G based on the current cross-platform CI evidence.
- Optional before final RC5 freeze: execute the Phase F probe in dedicated benchmark mode (`-s`/uncaptured output or artifact export) and archive per-scale latency values. These values should be treated as runner-specific observations, not universal performance guarantees.

## Release-gate interpretation

For the scope of this relational battery, RC5 is functionally green across Ubuntu and Windows through Phase G. The historical failures have known causes and validated corrections. The remaining Phase F timing capture is not a correctness blocker; it is a measurement-quality item.

## Result integrity

This document is cumulative by design. Historical failures must remain visible after fixes. Future RC5 findings should be appended with run ID, reproduction, diagnosis, correction and validation rather than rewriting earlier negatives as if they never occurred.
