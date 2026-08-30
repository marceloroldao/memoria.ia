# Memoria.ia Android Runtime Contract

Status: design/ABI freeze candidate for Issue #50.

Compatibility target: `integration/v1.0-candidate` at or after `b4d6363a99fc692283f3f10b2ae851648426794e`.

## Architectural rule

`OFF.IA/Kotlin -> Memoria.ia mobile boundary -> Resolutive-DB`

OFF.IA must not reimplement semantic/relational recall, provenance ranking, episodic/temporal recall, open-set abstention, or durable memory semantics.

## Required semantic parity

The Android runtime must expose behavior equivalent to the validated Product API for:

- conversational ingest (`/api/v1/conversation/ingest`);
- conversational resolve (`/api/v1/conversation/resolve`);
- provenance/source authority and ultimate-source lineage;
- explicit corrections/supersession;
- episode store (`/api/v1/episodes`);
- episode recall (`/api/v1/episodes/recall`);
- `HIT | MISS | UNRESOLVED` behavior;
- exact selected source context and memory/episode IDs;
- persistence/restart using Resolutive-DB on Android.

Examples such as cars, colors, poems, tools, voltages, reports, or projects are acceptance data only. The mobile runtime must not contain domain-specific rules for those examples.

## Native ABI

The public C ABI is declared in `include/memoria_mobile.h` and starts at ABI version 1.

The ABI intentionally uses opaque handles plus UTF-8 JSON request/response buffers. This keeps Kotlin/JNI bindings small while allowing the semantic payload to remain aligned with the Product API without exposing internal Python/C++ structures as ABI.

The ABI surface is:

- `memoria_mobile_open`;
- `memoria_mobile_learn_turn_json`;
- `memoria_mobile_resolve_context_json`;
- `memoria_mobile_store_episode_json`;
- `memoria_mobile_recall_episode_json`;
- `memoria_mobile_flush`;
- `memoria_mobile_close`.

## Persistence dependency

Android persistence is blocked on Resolutive-DB Issue #18, which must provide an Android NDK arm64-v8a compatible native persistence boundary. Memoria.ia remains owner of state semantics; BDR remains owner of durable persistence.

No SQLite substitution inside OFF.IA satisfies the Android parity requirement.

## Acceptance gate for Issue #50

Issue #50 remains open until all of the following are demonstrated:

1. Android arm64-v8a artifact builds in CI.
2. Kotlin/JNI can open Memoria.ia through the stable mobile boundary.
3. A learned conversational fact can be resolved by a paraphrased query in the same session.
4. Provenance identifies the authoritative source rather than an assistant echo.
5. Generic episode storage/recall works through the same boundary.
6. `UNRESOLVED` is preserved for low-confidence/ambiguous cases.
7. `flush -> process death -> reopen -> resolve` returns the same durable memory through BDR.
8. The full memory path works without network access.
9. OFF.IA contains no alternate semantic-memory implementation.

## Non-goals

This contract does not move llama.cpp into Memoria.ia, does not add MA2A, and does not define UI behavior. It defines only the stable mobile memory boundary required by OFF.IA.
