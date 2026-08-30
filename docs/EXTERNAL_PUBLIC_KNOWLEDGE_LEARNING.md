# External / Public Knowledge Learning

Tracking issue: **#114 — external/public knowledge learning with provenance for OFF.IA Curiosity**

## Purpose

Memoria.ia must be able to learn from public/external information acquired by consumers such as OFF.IA Curiosity, while preserving a hard distinction between personal/user-originated memory and externally sourced knowledge.

This is a Memoria.ia capability. OFF.IA must not reproduce memory semantics and must not write directly to Resolutive-DB / BDR.

## Ownership boundary

The invariant remains:

- **OFF.IA owns acquisition, orchestration and UI**;
- **Memoria.ia owns source classification, learning, semantic state, retrieval and provenance semantics**;
- **Resolutive-DB / BDR owns persistence**.

The required path is always:

`OFF.IA -> Memoria.ia -> BDR`

Never:

`OFF.IA -> BDR`

## Knowledge classes

Memoria.ia must distinguish at least two authority classes.

### Personal / local knowledge

Examples include user statements, preferences, personal events and conversation-derived state.

This knowledge is private/local by default and its provenance may identify the user/conversation as the originating authority.

### External / public knowledge

Examples include facts acquired from Wikipedia, official documentation, public Web pages, supported public APIs or future MA2A/public sources.

This knowledge must carry explicit external provenance and must never be persisted as if the user asserted it.

Suggested source classes include `external_import` and/or `public_web`; exact naming should follow the existing Memoria.ia provenance model.

## Required public contract

Memoria.ia needs an explicit versioned learning boundary for external knowledge. The exact ABI/API symbol should follow repository conventions, but conceptually it is equivalent to:

`learnExternalKnowledge(...)`

The contract must not be implemented as a consumer-side reuse of raw BDR records.

Minimum semantic input:

- normalized content/knowledge;
- external/public source class;
- source URL;
- source domain;
- source title;
- acquisition timestamp;
- optional excerpt/reference metadata;
- optional provider/source identifier;
- optional validation/confidence metadata;
- optional request/session correlation metadata that does not change semantic authority.

The result should expose learned memory IDs and enough status/provenance information for the consumer to audit the operation.

## Retrieval and offline learning loop

After successful learning, Memoria.ia must be able to retrieve the external knowledge later through its normal resolution/retrieval paths.

Expected behavior:

1. OFF.IA asks Memoria.ia to resolve a question.
2. If local knowledge is insufficient, OFF.IA may invoke Curiosity.
3. OFF.IA acquires public sources and performs local synthesis/validation.
4. According to user/app policy, OFF.IA submits approved knowledge to the external-learning contract.
5. Memoria.ia classifies and learns the knowledge with external provenance.
6. Memoria.ia persists it through BDR.
7. After restart, the knowledge is reconstructible from BDR-owned state.
8. A later question can retrieve that knowledge while the device is offline.

This converts Curiosity from a one-shot lookup into a durable learning path for Memoria.ia.

## Provenance requirements

At minimum, the provenance chain should preserve enough information to answer:

- Was this knowledge personal or external/public?
- Which source produced it?
- What URL/domain/title was associated with it?
- When was it acquired?
- Was it imported directly, synthesized or validated?
- Which memory record is the authoritative/ultimate source when relations or derived facts are created?

External provenance must survive BDR persistence and fresh-process reconstruction.

## Deduplication and conflict behavior

Repeated imports of the same fact/source must have deterministic behavior. Memoria.ia should avoid unbounded duplication while preserving evidence/provenance when the same fact appears from multiple sources.

Conflicts require explicit authority semantics. In particular:

- external content must not silently overwrite a personal fact;
- a personal assertion must not erase external-source provenance;
- contradictory external sources should remain distinguishable rather than collapsing into a false single authority;
- the resolver should be conservative when confidence/authority is insufficient.

## OFF.IA policy vs Memoria.ia semantics

OFF.IA may expose policies such as:

- never save Curiosity knowledge;
- ask before saving;
- automatically save validated Curiosity knowledge.

Those are OFF.IA product/orchestration policies.

Once learning is requested, source classification, deduplication, conflict handling, semantic storage and persistence belong exclusively to Memoria.ia.

## Android / mobile requirement

Because OFF.IA is the first consumer, the capability must be available through the supported Memoria.ia Android/mobile boundary if technically appropriate.

The mobile path must preserve the same durability rule already used by the runtime: logical memory state must be reconstructible after process death/restart from Memoria.ia -> BDR persistence.

## Future MA2A boundary

External/public knowledge may later become eligible for a MA2A/public knowledge layer.

This document does **not** require implementing MA2A transport now. It requires preserving provenance and authority metadata so that future routing can distinguish:

- personal/private local memory;
- public/external knowledge potentially eligible for sharing/federation.

Personal memories must not become MA2A/public merely because external knowledge exists in the same Memoria.ia instance.

## Acceptance criteria

- Public/versioned API or ABI for external/public knowledge learning.
- Clear source-authority distinction from personal/user-originated memory.
- URL/domain/title/acquisition provenance survives restart.
- External knowledge is retrievable later using normal Memoria.ia resolution/retrieval.
- Offline recall works after prior online Curiosity learning.
- No consumer-side BDR parsing/writing.
- Deterministic repeated-import/deduplication behavior.
- Explicit conflict behavior between personal and external knowledge.
- Android/mobile coverage for OFF.IA if this is the supported first integration path.
- Tests covering learning, provenance, restart, offline recall, deduplication and conflicts.
- Documentation of source authority and consumer responsibilities.

## Non-goals

This dependency does not authorize:

- blindly trusting arbitrary Web content;
- treating a public Web statement as a user assertion;
- OFF.IA reimplementing Memoria.ia semantics;
- OFF.IA writing directly to BDR;
- automatically publishing personal memory to MA2A;
- implementing the complete MA2A network as part of #114.
