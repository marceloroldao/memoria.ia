# Mobile Diagnostic Export

Status: experimental additive mobile ABI-v1 capability for Issue #55.

## Purpose

Provide OFF.IA and other mobile consumers with a read-only, portable diagnostic view of Memoria.ia state without parsing Resolutive-DB files or duplicating memory semantics outside Memoria.ia.

This is a **diagnostic export**, not a backup/restore format and not a raw BDR dump.

Architecture remains:

`OFF.IA -> Memoria.ia mobile ABI -> Resolutive-DB`

## C ABI

```c
memoria_mobile_status memoria_mobile_export_snapshot_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);
```

The function is additive to ABI v1. Existing ABI-v1 callers are unaffected. The returned buffer is owned by Memoria.ia and must be released with `memoria_mobile_free_buffer()`.

The operation is read-only: it must not advance the sequence, modify retrieval state, rewrite BDR, change authority/provenance, or alter later generated IDs.

## Request

The request is UTF-8 JSON. An empty object uses bounded defaults.

Supported pagination fields:

```json
{
  "turn_offset": 0,
  "turn_limit": 32,
  "episode_offset": 0,
  "episode_limit": 32
}
```

Rules:

- offsets are zero-based;
- negative offsets/limits are invalid;
- a limit of `0` means the default page size (`32`);
- each page is capped at `64` records;
- offsets beyond the current count return an empty page rather than exposing persistence internals.

Pagination bounds peak export memory use and allows Android to write/share larger diagnostics page-by-page.

## Response format

Current format identifier:

`memoria.mobile.diagnostic.v1`

Top-level fields include:

- `status`;
- `format`;
- public mobile `abi_version`;
- mobile persistence `state_schema`;
- `generated_at_unix`;
- `organization_id`;
- current generated-ID `sequence`;
- total turn/episode counts;
- turn and episode page metadata (`offset`, `limit`, `returned`, `next_offset`);
- paged `turns`;
- paged `episodes`.

Each exported turn contains, when available:

- `memory_id`;
- `role`;
- text;
- `source_type`;
- `ultimate_source_memory_id`;
- source authority;
- order;
- extracted relations with confidence and source memory ID.

Each exported episode contains, when available:

- `episode_id`;
- role/text;
- timestamp;
- event type;
- topic list representation;
- source type/authority;
- ultimate-source lineage;
- order;
- superseded state.

## Safety and privacy boundary

The diagnostic contains memory content because its purpose is inspection/debugging. Consumers should treat it as user data and require an explicit user action before writing or sharing it.

The export does not include:

- model files;
- API keys or provider secrets;
- raw BDR pages/files;
- filesystem paths;
- private implementation pointers.

OFF.IA must not infer or mutate memory semantics from this diagnostic representation. Retrieval, authority, provenance and persistence remain owned by Memoria.ia/BDR.

## Testing requirements

The mobile regression verifies that:

1. turn and episode IDs/content appear in the export;
2. UTF-8 Portuguese text round-trips;
3. pagination is bounded and deterministic;
4. export does not mutate the ID sequence;
5. retrieval is unchanged before/after export;
6. BDR-backed close/reopen preserves exported records.

A future streaming/chunk callback ABI may be introduced if the mobile runtime grows beyond the current bounded in-memory state. The versioned JSON format allows that transport change without making raw persistence a public contract.
