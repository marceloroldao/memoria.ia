# Structural equivalence V2 benchmark sequence

Execution order for issue #298:

1. `structural_equivalence_v2_probe.py` — epistemic sanity checks only.
2. Add stateful candidate/revocation implementation.
3. Add dense-hub and conflicting-equivalence adversarial cases.
4. Add persistence/restart serialization.
5. Add 100/1k/10k cost benchmark.
6. Only then expose an opt-in resolver path.
7. Re-run `v2_restart3_shared_fixture.py` unchanged.

The restart3 shared fixture remains a comparison probe, not a pass condition for early equivalence prototypes. A new prototype may remain `unresolved` until sufficient independent structural history exists. Failing closed is preferable to manufacturing semantic equivalence.
