# BDR v1.2.0-rc1 × Memoria.ia V2 — Initial Audit

Date: 2026-09-16

Status: audit completed before integration changes.

## Exact references

- Memoria.ia repository default branch: `main`.
- Memoria.ia `main` HEAD observed during audit: `cc543c57c21efa5ccfd59610aeedf7c891bc1dc1`.
- Actual experimental V2 line selected for this validation: `experiment/address-trajectory-v2` at `3a930902a9ab08fc68b6a29ef94f6ed1acf96a03`.
- Validation branch: `experiment/v2-bdr-v1.2.0-rc1-validation`, forked from that exact V2 SHA.
- Memoria package metadata on the V2 branch remains `1.0.0rc7`; V2 is an experimental architecture line, not a separately packaged V2 release.
- BDR repository default branch: `main`.
- BDR published candidate tag: `v1.2.0-rc1`.
- Annotated tag object: `1a17213f276c22d657853bc2fed83a707a22abc3`.
- Tag target / frozen candidate commit: `eb77ad7286f234243ca1ed1a2af2d55df8c12238`.
- Zenodo DOI: `10.5281/zenodo.22784729`.
- GitHub release is `prerelease=true`; v1.1.0 remains the stable BDR line.
- BDR `main` has already advanced past the frozen tag (observed HEAD `8a829af87455e30e02d48727a24ce00a38491c3d`, DOI documentation). Validation must therefore consume the tag/commit, never BDR main.

## CI / release evidence

- BDR CI run `35053229786` for frozen commit `eb77ad...` completed successfully.
- Memoria V2 head `3a930902...` has successful experimental PR regression run `34776318059`.
- The BDR release notes state the candidate surface includes `AtomicBDR`, `get`, `get_many`, `write_batch`, `put_many`, `erase_many`, `sync`, `last_sequence`, `durable_sequence`, Async/BatchSync/PerOperationSync, Atomic C ABI v2, packed-key reads, optional packed-output and fallback.
- Those release notes also retain scale evidence at 24/240/1200/5000/10000 against the earlier frozen topological/temporal Memoria workload at `99a1585d...`; that is useful prior evidence but is NOT validation of the current Address-Trajectory V2 head.

## Actual Memoria.ia V2 architecture found

The active experimental V2 is not the same architecture as the earlier frozen topological/temporal V1 sidecar.

`src/memoria_resolutiva/address_trajectory_v2.py` currently provides:

- mechanical NFC/casefold/whitespace canonicalization;
- unit decomposition without semantic regex/domain vocabulary;
- deterministic BLAKE2b `at2:` addresses;
- modality-neutral pre-addressed stream ingestion;
- append-only in-memory `AddressTrajectory` objects;
- immediate self-loop collapse;
- snapshot/restore of trajectory tuples;
- structural retrieval by overlap, ordered overlap and adjacency overlap;
- read-only resolution.

At this V2 slice, the module itself does NOT define a durable BDR adapter, entity model, explicit CURRENT/HISTORY temporal state, provenance object beyond `raw_text`/stream diagnostic provenance, epistemic state, conflict/reinforcement policy, ContextCompiler, ResponseValidator or Learning Gate. Those capabilities exist in other/frozen Memoria lines, but they must not be falsely attributed to this V2 module or imported merely to make this validation pass.

Therefore the validation must distinguish:

1. V2-native contracts that actually exist (deterministic addresses, trajectory order, raw text, snapshot/restore, structural resolve, read-only query, deterministic restart once persistence is supplied); and
2. requested semantic surfaces that are absent from this V2 slice and must be reported as `not implemented / not applicable`, not invented during this integration task.

## Existing persistence / comparison infrastructure

The repository already contains a mature topological/temporal persistence experiment from PR #276 and related BDR integration lineage. It maps Memoria-owned records to atomic BDR logical batches and uses SQLite as a comparative oracle. BDR issue #25 defines the original atomic Python bridge acceptance fixture (`azul -> preta -> branca`); BDR PR #26 documents the shared atomic C ABI bridge.

This infrastructure is reusable as test/adapter precedent, but the V2 Address-Trajectory state schema must remain V2-owned and generic. The old topology/epistemic schema must not be silently treated as V2 semantics.

## Relevant open work

Memoria V2 currently has open PR #296 (`experiment: address-trajectory cognitive resolver V2`) and CI-only PR #297. Open V2 issues include #298 (emergent structural equivalence), #299 (adversarial acceptance), #300 (revocation/conflict), #301 (scale), #302 (shared restart3 corpus), #303 (opt-in resolver integration), #304 (lineage independence), #305 (performance cache), #306 (no-semantic-shortcuts guard), #307/#308 (promotion/direct-evidence precedence), and #309 (transferable topological roles).

Persistence-related historical/open work includes Memoria PR #276 and BDR issue #25 / PR #26. BDR PR #26 remains open/draft historically even though the published RC1 now contains the promoted candidate surface; validation will use only the published RC1 tag.

## Discrepancies from task assumptions

1. `main` is not the current V2 implementation. The V2 under active development is `experiment/address-trajectory-v2` at `3a930902...`. This validation branch is therefore based on that V2 head rather than `main`.
2. The current V2 slice is trajectory-centric and in-memory. It does not yet implement the full topological/temporal/epistemic contract listed in the task. Missing V2 features will not be implemented merely for BDR validation.
3. BDR `main` is newer than the published RC1 tag. The RC1 tag correctly resolves through annotated tag object `1a17213...` to frozen commit `eb77ad...`; this exact commit is the only BDR code eligible for this validation.
4. Existing 24/240/1200/5000/10000 BDR evidence was generated against Memoria commit `99a1585d...`, not the current V2 head. It cannot substitute for a fresh V2 integration run.

## Initial blocker decision

No published-tag mismatch or corruption blocker was found. The published BDR RC1 identity is reproducible and CI-green. Proceed with baseline and an additive V2 persistence validation, preserving the current V2 semantics and using isolated fixtures only.
