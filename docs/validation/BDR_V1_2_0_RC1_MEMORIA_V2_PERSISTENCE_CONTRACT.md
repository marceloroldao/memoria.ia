# Minimal persistence contract — Address-Trajectory V2 × BDR v1.2.0-rc1

Date: 2026-09-16

This contract freezes only semantics already owned by `AddressTrajectoryMemory`. It does not import CURRENT/HISTORY/entity/epistemic semantics from earlier topological experiments.

## Authoritative V2 state

For each `AddressTrajectory`, persistence must preserve exactly:

- `trajectory_id`;
- `raw_text` (including empty diagnostic provenance for addressed streams);
- ordered `addresses` tuple;
- ordered `surfaces` tuple.

The collection order returned by `snapshot()` is authoritative. Restore must also recover the next trajectory identifier according to the existing `restore()` behavior.

## Determinism invariants

1. Persist -> close -> reopen -> restore must produce an equal snapshot.
2. Deterministic `at2:` addresses must not change because of persistence or restart.
3. Resolve results for the same query and limit must be equal before and after restart.
4. Empty values, UTF-8 text and arbitrary address strings must round-trip without lossy normalization in the persistence codec.
5. Storage must not reinterpret raw text, surfaces, addresses or trajectory IDs.
6. A logical trajectory mutation must be represented as one atomic BDR batch when multiple physical records are used.
7. Partially committed trajectory state must never be exposed after recovery.

## Storage boundary

Memoria.ia owns record keys/schema, serialization and reconstruction. BDR owns byte durability, atomic batches, sequence counters, bulk retrieval, WAL/recovery and storage integrity.

No Memoria-specific entity, temporal, epistemic, conflict or reinforcement logic may be added to BDR.

## Published BDR pin

Only:

- tag: `v1.2.0-rc1`;
- commit: `eb77ad7286f234243ca1ed1a2af2d55df8c12238`;
- DOI: `10.5281/zenodo.22784729`.

BDR `main` and locally modified BDR builds are invalid validation targets.

## Requested task surfaces absent from this V2 slice

The Address-Trajectory V2 module does not currently define semantic CURRENT/HISTORY, entity aliases, epistemic truth/conflict/reinforcement, Context Compiler, Response Validator or Learning Gate. Those are therefore recorded as `NOT_IMPLEMENTED_IN_CURRENT_V2_SLICE` for this validation rather than implemented solely to satisfy the database test.

## Rollback boundary

The adapter must be additive and opt-in. Existing persistence paths remain untouched. All BDR fixtures use isolated temporary databases. Removing the adapter/configuration must restore the exact pre-integration V2 behavior without data migration.
