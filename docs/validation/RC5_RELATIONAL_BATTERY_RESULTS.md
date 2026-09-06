# RC5 Relational Memory Validation Battery — Results Log

Target: `v1.0.0-rc5`

Functional freeze commit: `06c747478e05ee11ab2c5c3c24cf75365262b872`

Release preparation commit: `1efced0caceb00ce16cebcdd98338631d254182d`

Validation branch: `test/rc5-relational-battery`

Policy: record positive and negative results. Failures are not hidden or rewritten as passes. Any unexpected behavior must be retained here with reproduction details.

## Phase A — Native deterministic relational core

Status: PARTIAL PASS / CROSS-PLATFORM REGRESSION UNDER CORRECTION

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B01 | Multi-hop | Alt → gato → animal → ser-vivo plus weaker direct edge | 3-hop path ranked above weak direct path; evidence IDs preserved | PASS on Ubuntu full regression |
| RC5-B02 | Directionality | Query reverse ser-vivo → Alt without reverse edges | UNRESOLVED | PASS on Ubuntu full regression |
| RC5-B03 | Bounded traversal | Valid target requires 3 hops while max_hops=2 | UNRESOLVED | PASS on Ubuntu full regression |
| RC5-B04 | Ambiguity | Direct edge marked ambiguous | UNRESOLVED | PASS on Ubuntu full regression |
| RC5-B05 | Confidence | Weak edge confidence 0.30 with threshold 0.80 | UNRESOLVED | PASS on Ubuntu full regression |
| RC5-B06 | Cycle protection | Graph contains animal → Alt cycle | terminate and still return intended 2-hop path | PASS on Ubuntu full regression |

### Cross-platform regression result — run 34006309839

- Ubuntu: PASS — full regression completed successfully.
- Windows: FAIL — 622 passed, 28 skipped, 9 errors, 2 warnings.
- The 9 Windows errors are all setup errors in `tests/test_native_python_concept_rewrite_parity.py`.
- Root cause observed: the C compilation command succeeds, but the fixture expects an output path without the Windows `.exe` suffix and therefore `output.is_file()` returns false. This is a test-harness portability defect; the log does not show a semantic mismatch in the nine rewrite cases.
- Negative result is retained because RC5 is not cross-platform green until the harness is corrected and rerun.

### Cross-platform regression result — run 34033799428

- Ubuntu: PASS — full regression completed successfully.
- Windows: FAIL — 630 passed, 28 skipped, 1 failed, 2 warnings.
- The `.exe` harness defect was corrected successfully: eight of the nine native/Python rewrite parity cases passed.
- Remaining failure: `qual a diferença de potencial do charger`.
- Python reference: `REWRITTEN`; native Windows CLI: `UNCHANGED`.
- Diagnosis: Windows narrow `argv` transformed the UTF-8 query before it reached the native kernel. The failure is at the CLI test boundary, not yet evidence of a kernel-level UTF-8 mismatch.
- Corrective test change: native parity CLI now reads the query from UTF-8 stdin rather than narrow `argv`; the Python harness explicitly writes UTF-8. This preserves the original Portuguese phrase and will be validated by the next CI run.

## Phase B — Directional type collection / taxonomy matrix

Status: PENDING CI

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B07 | Type collection | Alt and Luna are gatos; Rex is cachorro | gato collection returns only Alt and Luna | PENDING CI |
| RC5-B08 | Taxonomy direction | gato is animal | animal collection returns direct member gato, not transitive Alt/Luna | PENDING CI |
| RC5-B09 | Parallel type isolation | Rex is cachorro while cats and taxonomy coexist | cachorro collection returns only Rex | PENDING CI |
| RC5-B10 | Namespace isolation | Nina is gato only in session-b | session-b gato collection returns Nina only | PENDING CI |
| RC5-B11 | Supersession | Milo→gato evidence is superseded | Milo excluded from active gato collection | PENDING CI |
| RC5-B12 | Attribute contamination | gato has pelos | pelos relation never appears as gato membership | PENDING CI |

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

## Next phases

- Phase C: resolver precedence (direct HIT > relation inference > collection > neighborhood > UNRESOLVED).
- Phase D: namespace and supersession adversarial matrix.
- Phase E: persistence/restart consistency.
- Phase F: scale/performance at increasing relation counts.
- Phase G: conversational corpus with mixed people, animals, vehicles, colors, corrections and indirect questions.

## Result integrity

This file is intended to remain cumulative. Negative findings must stay visible after fixes, with the later fixed result appended rather than deleting the original failure.
