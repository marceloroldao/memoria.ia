# V2 — Incremental witnessed episodes (local-only opt-in)

`MEMORIA_EXTERNAL_EPISODE_PERSISTENCE=sqlite-incremental` activates a
dedicated **durable storage backend in the existing Memoria.ia V2 service**.
It retains the exact typed `/api/v1/external/episodes` contract and the real
`EvidenceCore` for projection. The legacy full-snapshot route remains the
default when this environment variable is absent.

Requires `MEMORIA_STORAGE_BACKEND=sqlite` and
`MEMORIA_STORAGE_ALLOW_FALLBACK=false`. Each episode is stored once as
a canonical source envelope in a SQLite WAL database under
`MEMORIA_DATA_DIR/external-episodes-incremental/`. The transaction is
committed with `synchronous=FULL` before returning a receipt. The receipt has
`backend=sqlite-incremental`,
`state_id=external-episode:<record_key>` and
`sha256=<content_sha256>`. It is not a remote/server synchronization receipt.

On restart, every row is revalidated (Pydantic schema, SHA-256 source
identity, canonical payload, digest, ID/world/tick index), then reinserted
into a fresh genuine V2 `EvidenceCore`. Duplicate requests use the indexed
`record_key` and do not write. The same key with changed content returns
409; invalid digests never receive an ACK. Once a projection fails after a
durable commit, the service refuses further ACKs until a restart rebuilds
from the journal.

The migration step also reads any existing legacy
`ProductEvidenceService` receipt from `MEMORIA_DATA_DIR/evidence`, verifies
that **all** rows are the expected observed episodes, and copies them
idempotently into the incremental journal. Original snapshots and receipt
are preserved. Any unrelated or inconsistent legacy row blocks startup;
no automatic truncation, overwrite or destructive format occurs.

The authenticated `/api/v1/external/episodes/health` reports the active
mode and observed count. Other EvidenceCore functionality and endpoints
retain their current backend. The incremental external graph is specifically
for witnessed episodes, not an assertion that all V2 subsystems were migrated.

## Isolated VM measurements, 2026-09-29

Source: this V2 branch on Live's VM, Python 3.14, SQLite WAL,
10,000 distinct valid witnessed episodes and one source-backed
`observed_experience` relation per episode. Values include SQLite journal
and WAL files **during** ingestion; not a long-term disk-capacity guarantee.

| Episodes | Bytes occupied during test |
|---:|---:|
| 100 | 1,932,096 |
| 1,000 | 5,279,296 |
| 10,000 | 16,461,568 |

10,000 committed observations: 5.77 s in isolated scratch test.
Cold reopen + validation + EvidenceCore replay: 2.27 s for 10,000 relations.
Peak process RSS in the same test: ~82 MiB. The results include a single
VM run, not a long-duration production load test.

Compared with the old full-graph-snapshot-per-episode implementation, the
incremental journal eliminates accumulating historical graph snapshots.
The local app's bounded ingest cursor remains a **separate** responsibility:
advance only after verifying the returned durable receipt. The world
Single Writer and Godot must never depend on this service's availability.
