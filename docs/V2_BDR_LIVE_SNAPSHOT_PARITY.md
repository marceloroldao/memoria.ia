# Live SQLite → BDR shadow mirror (observational only)

`scripts/mirror_external_episode_live_snapshot.py` makes a private BDR candidate
from one consistent backup of the *incremental external-episode SQLite journal*.
It does not change the Live backend, touch the Nov world, advance its ingest
checkpoint, stop the local timer, call the server API, or contact the central
Memoria.ia service.

## Snapshot and verification contract

- The source SQLite database is opened with URI `mode=ro`; SQLite's online
  backup API copies committed records including WAL into a distinct private
  snapshot. The producer may keep writing. The snapshot is one consistent
  point-in-time view, not a claim that BDR is current after copying.
- Inputs are restricted to a 256 MiB source footprint (DB + WAL + SHM),
  200,000 observations, and a minimum available-space budget before copying.
  The output directory must not exist and is created with mode 0700.
- Each source record is validated using the existing typed V2 contract,
  canonical bytes, full identity and content digests, evidence ID, world,
  episode ID and logical tick. Every source row maps to the exact BDR
  identity and sequence indexes. The complete V2 EvidenceCore edge stream
  must match, including source text, provenance and epoch.
- The BDR candidate is closed and reopened, then all rows and edges are
  compared a second time. Native last and durable sequences must match.
- An optional existing local Nov checkpoint is read twice, never written.
  Its *initial* last acknowledged record/digest must exist in the snapshot.
  The report explicitly says whether the checkpoint changed while copying.
  If it changed, this is not a cutover-ready checkpoint. Do not use the
  mirrored snapshot to claim that newer episodes have been copied.
- The private report contains counts, stream digests, elapsed time, disk
  consumption and authority flags. No raw episodes, keys, tokens, ledger
  content or identifying addresses are logged. The copied private SQLite
  snapshot and BDR files remain sensitive and are **not** a public artifact.
- Missing native library, changed/corrupt source, invalid checkpoint,
  mismatched indexes or graph, insufficient space and existing output
  destination are fatal. Partial output remains private for inspection and
  must not be used as a valid mirror without `parity-report.json`.

## Example, authorized local service account only

```bash
PYTHONPATH=/path/to/pinned/memoria/src:/path/to/pinned/resolutive-DB \
  python scripts/mirror_external_episode_live_snapshot.py \
  --sqlite-source /var/lib/live-infinita/memoria-local/external-episodes-incremental/external-episodes.sqlite3 \
  --checkpoint /var/lib/live-infinita/memoria-local/nov-ingest.checkpoint.json \
  --bdr-library /path/to/verified/libbdr_atomic_c_api.so \
  --output /var/lib/live-infinita/memoria-local/bdr-mirrors/NEW_UNIQUE_RUN
```

The pinned BDR native ABI is `resolutive-DB v1.2.0-rc4`, commit
`317882a00f041fc1568ff986af8016b09453f21a`. Use the exact Memoria.ia
release commit containing this script and candidate adapter. The Live
repository owns its own operator/deploy wrapper, which must verify both
pins and **never** restart or modify Nov, Godot, the local writer or cursor.

The current deployed SQLite remains authoritative for local derived memory.
BDR is observational only and never authoritative for the World State.
