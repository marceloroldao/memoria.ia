# RC5 Relational Memory Validation Battery — Results Log

Target: `v1.0.0-rc5`

Functional freeze commit: `06c747478e05ee11ab2c5c3c24cf75365262b872`

Release preparation commit: `1efced0caceb00ce16cebcdd98338631d254182d`

Validation branch: `test/rc5-relational-battery`

Policy: record positive and negative results. Failures are not hidden or rewritten as passes. Any unexpected behavior must be retained here with reproduction details.

## Phase A — Native deterministic relational core

Status: RUNNING

| ID | Area | Scenario | Expected | Result |
|---|---|---|---|---|
| RC5-B01 | Multi-hop | Alt → gato → animal → ser-vivo plus weaker direct edge | 3-hop path ranked above weak direct path; evidence IDs preserved | PENDING CI |
| RC5-B02 | Directionality | Query reverse ser-vivo → Alt without reverse edges | UNRESOLVED | PENDING CI |
| RC5-B03 | Bounded traversal | Valid target requires 3 hops while max_hops=2 | UNRESOLVED | PENDING CI |
| RC5-B04 | Ambiguity | Direct edge marked ambiguous | UNRESOLVED | PENDING CI |
| RC5-B05 | Confidence | Weak edge confidence 0.30 with threshold 0.80 | UNRESOLVED | PENDING CI |
| RC5-B06 | Cycle protection | Graph contains animal → Alt cycle | terminate and still return intended 2-hop path | PENDING CI |

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

- Phase B: collection/type stress and taxonomy contamination.
- Phase C: resolver precedence (direct HIT > relation inference > collection > neighborhood > UNRESOLVED).
- Phase D: namespace and supersession adversarial matrix.
- Phase E: persistence/restart consistency.
- Phase F: scale/performance at increasing relation counts.
- Phase G: conversational corpus with mixed people, animals, vehicles, colors, corrections and indirect questions.

## Result integrity

This file is intended to remain cumulative. Negative findings must stay visible after fixes, with the later fixed result appended rather than deleting the original failure.
