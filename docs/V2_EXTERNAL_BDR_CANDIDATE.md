# Experimental Memoria.ia V2 external observed episodes — native BDR candidate

This branch benchmarks a future storage backend; **it is not a production
option**. The Live Infinita instance continues to use
\`MEMORIA_EXTERNAL_EPISODE_PERSISTENCE=sqlite-incremental\`, with the
authoritative Nov World State and Godot untouched.

## Native path, pinned

- \`resolutive-DB\` published tag \`v1.2.0-rc4\` at commit
  \`317882a00f041fc1568ff986af8016b09453f21a\`.
- Its actual compiled \`libbdr_atomic_c_api.so\` and
  \`bdr.atomic.AtomicBDR\` are used. C ABI must report version 2.
- \`BDR_ATOMIC_LIBRARY\` explicitly identifies the native library. Missing
  library fails, **never silently falls back to SQLite**.
- The existing V2 \`EvidenceCore\` is used for all cognition and replay;
  \`BdrExternalEpisodeCandidate\` is only the persistence/index adapter.
- No native library or BDR service is installed on the production Live VM
  by the candidate PR or by its CI.

The older \`BDRResolutiveMemory.add()\` adapter slices and indexes every
byte of each logical payload, and V2's legacy ProductEvidenceService stores
complete graph snapshots. Neither is appropriate for repeated external
episode receipts. This experiment instead persists **the single canonical
observed envelope** and its indexes, using an atomic batch of:

\`external:v1:id:<64-hex-record-key>\` → original canonical source,
\`external:v1:seq:<16-digit-n>\` → full record key,
\`external:v1:count\` → n + 1, and a format marker on the first batch.

All fields are one \`BATCH_SYNC\` transaction. The ACK requires native
\`durable=true\` and \`durable_sequence >= batch.sequence\`. Source and
indexes are not acknowledged separately. Duplicate identity with identical
content is idempotent; same key with changed content fails. Startup rejects
missing or corrupt metadata, dangling indexes, invalid canonical source
or a native durability gap, and rebuilds the real V2 graph in index order.

## Migration mechanics

\`mirror_sqlite_snapshot(sqlite_path)\` is a side-by-side **copy only**.
It opens the current incremental SQLite observation journal in read-only
mode, verifies each record through V2's typed schema, full identity digest
and canonical payload, then inserts it into a *different scratch BDR root*.
Original SQLite files and the Live checkpoint are never modified. Duplicate
observations re-copy idempotently. No production cursor is transferred or
advanced by this experiment.

A future actual migration must explicitly quiesce **only the local mirror
worker**, capture the authoritative SQLite record count and hashes, mirror
the source, compare identical source+graph+latest cursor and then switch the
backend behind a rollback gate. Nov and Godot must continue uninterrupted.
Only after cold restart and recovery tests would BDR become authoritative
for the *local derived memory*; it never becomes authoritative for World State.

## Release gates

1. Both backends process the same 100, 1,000 and 10,000 typed observations,
   with exact per-record identity/content hashes and full EvidenceCore-edge
   parity (subject, predicate, object, source, origin, epoch).
2. Both recover the full history after cold restart. Repeating a record
   cannot create extra relations or change the BDR native sequence.
3. One logical observation+index+count must consume one native atomic
   sequence; BDR must report the sequence durable **before** returning ACK.
4. Torn BDW4 final transaction must recover the previous complete record
   and reject half-persisted data/indexes. Test deliberate corruption,
   restart after forced termination, conflicting duplicate, and source
   rotation/truncation in isolated fixtures.
5. Report elapsed ingest and replay time, disk used *during* and after
   operation (including WAL), and peak RSS. Assess against Live VM resource
   limits; do not equate equal record counts with equal I/O or index work.
6. A production switchover must preserve the old SQLite and checkpoint,
   require explicit operator approval, and have a reversible cutover
   that touches neither Single Writer nor the stream renderer.

The script \`scripts/benchmark_external_episode_bdr.py\` only uses temporary
directories and synthetic *structurally valid* Nov observations, never the
production source ledger or credentials.

Example in an isolated environment after building the tagged BDR library:

\`\`\`bash
python scripts/benchmark_external_episode_bdr.py \
  --bdr-library /path/to/libbdr_atomic_c_api.so --scale 1000
\`\`\`

Until these gates are satisfied, the SQLite incremental local memory remains
the only deployed persistence backend.
