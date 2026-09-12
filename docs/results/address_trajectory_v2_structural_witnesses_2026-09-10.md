# Address-Trajectory V2 — Automatic Structural Witnesses

Date: 2026-09-10
Status: experimental; gate passed; not qualified for production/mobile merge.
Canonical PR: #296 (draft)
Head under test: `f5e655041655bff669667198edc5db8d524b95e5`
CI run: #417 / `34487530789`

## Result

The first topology-only automatic witness detector passed the experimental regression gate on Ubuntu and Windows while preserving the exact frozen restart3 reference and BDR/topological parity.

- Ubuntu: 932 passed, 35 skipped.
- Windows: 932 passed, 35 skipped.
- frozen restart3 reference: success.
- BDR/topological parity: success.

## Discovery rule

A witness is not supplied as an equivalence label. It is derived from stored trajectory occurrences. Two distinct source configurations may produce a witness only when independent lineages converge through the same contiguous structural bridge immediately before the same terminal region.

A shared terminal alone is insufficient. A hyperdense shared bridge fails closed. Repeated occurrences are grouped by source signature and witness production is bounded per pair.

Current structural safety bounds are explicit operational limits, not learned cognitive weights:

- `min_bridge_addresses = 2`
- `max_bucket_signatures = 32`
- `max_witnesses_per_pair = 8`

These values require later acceptance analysis. Their conservative failure mode is increased unresolved rate, never forced equivalence.

## Scaling evidence

| Scale | Occurrences | True witnesses | Dense-hub witnesses | Discovery time | Peak Python allocation |
|---:|---:|---:|---:|---:|---:|
| 100 | 104 | 2 | 0 | ~0.68 ms | 21,763 B |
| 1,000 | 1,004 | 2 | 0 | ~5.03 ms | 203,330 B |
| 10,000 | 10,004 | 2 | 0 | ~51.78 ms | 2,013,914 B |

The genuine A/B convergence remained `supported` with two independent witnesses at every scale.

### Recurrent two-origin stress

A second fixture alternates only two valid structural origins through the same bridge. The detector groups occurrences by origin signature and emits at most eight witnesses rather than performing a full pairwise occurrence scan.

| Scale | Witnesses emitted | Discovery time | Peak Python allocation |
|---:|---:|---:|---:|
| 100 | 8 | ~0.57 ms | 8,386 B |
| 1,000 | 8 | ~3.79 ms | 46,375 B |
| 10,000 | 8 | ~41.97 ms | 481,311 B |

## Adversarial conclusions

Passed:

- independent repeated convergence can support an equivalence;
- same-lineage replay cannot create a witness;
- one accidental pair remains only a candidate;
- terminal-only hub sharing produces no witness;
- hyperdense shared bridge produces no witness;
- multimodal addresses participate without text semantics;
- detector does not create transitive closure;
- output is deterministic under input order;
- recurrent two-origin evidence remains bounded.

## Negative evidence and open risks

The frozen Lotus/Vibe plural query remains unresolved in V2. This is preserved intentionally. The detector derives local trajectory convergence; it does not provide a cold-start linguistic prior and was not tuned with cat/name/plural rules.

Performance debt remains elsewhere in V2:

- structural-equivalence-state lookup is ~75.7 ms at 20,004 events;
- multiscale adversarial query is ~270 ms mean at 10k trajectories because hierarchy construction/indexing still needs optimization.

The current witness detector uses the configured minimal bridge width as the index geometry. Finer multiscale bridge geometry may be explored later, but must not reintroduce an O(n^2) global occurrence scan.

`lineage_id` and `occurrence_id` remain provenance inputs. The system deliberately does not infer independence from trajectory IDs or repetition because copies/replays/derived outputs must not become false independent evidence.

## Decision

Automatic topology-derived witness discovery is promising enough to remain in the V2 experimental path. It is not sufficient to merge PR #296 or replace restart3. The next gate is preservation of multiple competing futures per equivalent signature, followed by structural-pattern generalization on held-out address configurations.
