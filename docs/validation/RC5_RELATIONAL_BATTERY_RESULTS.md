# RC5 Relational Memory Validation Battery — Results Log

Target: `v1.0.0-rc5`

Functional freeze commit: `06c747478e05ee11ab2c5c3c24cf75365262b872`

Release preparation commit: `1efced0caceb00ce16cebcdd98338631d254182d`

Validation branch: `test/rc5-relational-battery`

Policy: record positive and negative results. Failures are not hidden or rewritten as passes. Any unexpected behavior must be retained here with reproduction details.

## Phase A — Native deterministic relational core

Status: PASS / CROSS-PLATFORM GREEN

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B01 | Multi-hop | Alt → gato → animal → ser-vivo plus weaker direct edge | 3-hop path ranked above weak direct path; evidence IDs preserved | PASS |
| RC5-B02 | Directionality | Query reverse ser-vivo → Alt without reverse edges | UNRESOLVED | PASS |
| RC5-B03 | Bounded traversal | Valid target requires 3 hops while max_hops=2 | UNRESOLVED | PASS |
| RC5-B04 | Ambiguity | Direct edge marked ambiguous | UNRESOLVED | PASS |
| RC5-B05 | Confidence | Weak edge confidence 0.30 with threshold 0.80 | UNRESOLVED | PASS |
| RC5-B06 | Cycle protection | Graph contains animal → Alt cycle | terminate and still return intended 2-hop path | PASS |

### Cross-platform regression result — run 34006309839

- Ubuntu: PASS — full regression completed successfully.
- Windows: FAIL — 622 passed, 28 skipped, 9 errors, 2 warnings.
- The 9 Windows errors are all setup errors in `tests/test_native_python_concept_rewrite_parity.py`.
- Root cause observed: the C compilation command succeeds, but the fixture expects an output path without the Windows `.exe` suffix and therefore `output.is_file()` returns false. This is a test-harness portability defect; the log does not show a semantic mismatch in the nine rewrite cases.
- Negative result retained for audit history.

### Cross-platform regression result — run 34033799428

- Ubuntu: PASS — full regression completed successfully.
- Windows: FAIL — 630 passed, 28 skipped, 1 failed, 2 warnings.
- The `.exe` harness defect was corrected successfully: eight of the nine native/Python rewrite parity cases passed.
- Remaining failure: `qual a diferença de potencial do charger`.
- Python reference: `REWRITTEN`; native Windows CLI: `UNCHANGED`.
- Diagnosis: Windows narrow `argv` transformed the UTF-8 query before it reached the native kernel.
- Negative result retained for audit history.

### Cross-platform regression result — run 34034430288

- Ubuntu: PASS.
- Windows: PASS.
- UTF-8 parity fix validated: the native test CLI now receives the query via UTF-8 stdin, avoiding Windows narrow-argv code-page conversion.
- Result: the Portuguese phrase `qual a diferença de potencial do charger` now preserves native/Python parity.
- This closes the test-boundary defect without weakening the Portuguese test case.

## Phase B — Directional type collection / taxonomy matrix

Status: PASS IN GREEN CROSS-PLATFORM REGRESSION

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B07 | Type collection | Alt and Luna are gatos; Rex is cachorro | gato collection returns only Alt and Luna | PASS |
| RC5-B08 | Taxonomy direction | gato is animal | animal collection returns direct member gato, not transitive Alt/Luna | PASS |
| RC5-B09 | Parallel type isolation | Rex is cachorro while cats and taxonomy coexist | cachorro collection returns only Rex | PASS |
| RC5-B10 | Namespace isolation | Nina is gato only in session-b | session-b gato collection returns Nina only | PASS |
| RC5-B11 | Supersession | Milo→gato evidence is superseded | Milo excluded from active gato collection | PASS |
| RC5-B12 | Attribute contamination | gato has pelos | pelos relation never appears as gato membership | PASS |

## Phase C — Resolver precedence contract

Status: PASS IN GREEN CROSS-PLATFORM REGRESSION

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B13 | Direct precedence | Base resolver returns anything except UNRESOLVED | Return immediately; no relational mode may override direct/base result | PASS |
| RC5-B14 | Relation vs collection | Base misses and query can enter relational inference | Relation inference is evaluated before type collection | PASS |
| RC5-B15 | Collection vs neighborhood | Relation inference does not resolve | Type collection is evaluated before one-hop neighborhood | PASS |
| RC5-B16 | Final fallback | No direct, relation, collection or neighborhood resolution | Remain UNRESOLVED | PASS |

The contract test `tests/test_rc5_resolver_precedence_contract.py` asserts the frozen bridge ordering directly from `concept_relation_resolve_bridge.c` so accidental reordering becomes a release-blocking regression.

## Phase D — Namespace and supersession adversarial matrix

Status: PASS / CROSS-PLATFORM GREEN — run 34034750890

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B17 | Namespace contradiction | `charger→34v` in session-a and `charger→99v` in session-b | session-a never resolves 99v | PASS |
| RC5-B18 | Superseded dominance | superseded `charger→danger` has confidence 1.00; active `charger→safe` has 0.90 | danger excluded; safe resolves | PASS |
| RC5-B19 | Duplicate active evidence | same `charger→34v` edge appears with 0.95 and 0.82 evidence | both active paths retained and ranked by confidence | PASS |
| RC5-B20 | Cross-namespace false path | session-b has `charger→99v→danger` | path exists only in session-b, never session-a | PASS |
| RC5-B21 | Superseded foreign value | session-b superseded `charger→120v` at confidence 1.00 | 120v remains UNRESOLVED | PASS |
| RC5-B22 | Empty namespace isolation | empty namespace has `charger→12v` | only empty namespace resolves 12v | PASS |

Dedicated native matrix: `native/mobile/tests/rc5_namespace_supersession_matrix.c`.
Pytest cross-platform wrapper: `tests/test_rc5_namespace_supersession_matrix.py`.

## Phase E — Persistence / restart consistency

Status: PASS / CROSS-PLATFORM GREEN — run 34038779945

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B23 | Durable sync | Active and superseded lineage state is written and synced | sync succeeds before shutdown | PASS |
| RC5-B24 | Close/reopen | Persistence is closed and reopened against the same data path and organization | reopen succeeds using persisted state | PASS |
| RC5-B25 | Supersession after restart | derived memory invalidated by corrected parent before shutdown | derived remains inactive after reopen | PASS |
| RC5-B26 | Active correction after restart | replacement `b-new` is active before shutdown | `b-new` remains active after reopen | PASS |
| RC5-B27 | Build integration | native lineage restart executable remains wired into mobile test build | restart regression cannot silently disappear from CMake | PASS |

Runtime evidence in `native/mobile/tests/lineage_state.c` performs a real save → sync → close → reopen → resolve sequence. `tests/test_rc5_persistence_restart_contract.py` freezes those restart invariants in the standard cross-platform pytest regression.

## Phase F — Scale / performance probe

Status: PENDING CI

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B28 | 100 edges | bounded 4-hop traversal in a 100-edge chain | correct path preserved; timing recorded | PENDING CI |
| RC5-B29 | 1,000 edges | bounded 4-hop traversal in a 1,000-edge chain | correct path preserved; timing recorded | PENDING CI |
| RC5-B30 | 10,000 edges | bounded 4-hop traversal in a 10,000-edge chain | correct path preserved; timing recorded | PENDING CI |
| RC5-B31 | 50,000 edges | bounded 4-hop traversal in a 50,000-edge chain | correct path preserved; timing recorded; no runaway | PENDING CI |

Native probe: `native/mobile/tests/rc5_relation_scale.c`.
Cross-platform wrapper: `tests/test_rc5_relation_scale.py`.

Timing policy: shared GitHub Actions runner timings are observational, not absolute performance claims. The test records latency at each relation count and uses only a deliberately generous 30-second runaway guard at 50,000 edges. Functional correctness is still mandatory at every scale point.

## Existing RC5 deterministic coverage observed before this run

The frozen repository already contains native regression coverage for:

- collection by type (`Quais gatos você conhece?`);
- exclusion of taxonomy targets from type membership;
- exclusion of attribute-like relations from membership;
- namespace isolation;
- superseded evidence exclusion;
- English collection-query extraction;
- fail-closed behavior for unsupported collection phrasing;
- multi-hop path ordering by confidence;
- evidence-ID preservation;
- weak-edge rejection;
- ambiguous-edge rejection;
- cycle protection.

These existing tests are treated as regression prerequisites, not as substitutes for the new battery.

## Next phase

- Phase G: conversational corpus with mixed people, animals, vehicles, colors, corrections and indirect questions.

## Result integrity

This file is intended to remain cumulative. Negative findings must stay visible after fixes, with the later fixed result appended rather than deleting the original failure.
