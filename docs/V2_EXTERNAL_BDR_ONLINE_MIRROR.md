# Online SQLite → native BDR mirror proof (experimental, no cutover)

The read-only mirror is separate from the Live runtime. It proves that a
point-in-time copy of the SQLite WAL journal can be fully reconstructed in
native BDR while the authoritative SQLite process is still running. It does
**not** change \`MEMORIA_EXTERNAL_EPISODE_PERSISTENCE\`, API endpoints, any
checkpoint, Nov, Godot, or the central Memoria.ia server.

## Capture and validation

- Open the source SQLite database using \`mode=ro\`, and use the SQLite
  **online backup API** to obtain a consistent snapshot. Copying the main
  \`.sqlite3\` file without its live WAL is explicitly prohibited.
- Use a new output directory with 0700 permissions and reject overwrite.
  This directory contains the isolated SQLite snapshot, BDR candidate,
  and a private proof JSON; no secrets or raw observation text are logged.
- Verify \`PRAGMA integrity_check=ok\`; open the snapshot through the actual
  V2 incremental store (which validates every canonical source row).
- Mirror to pinned native BDR v1.2.0-rc4 with the existing V2 candidate.
  Check all count, ordered full record keys, content digests, canonical source
  bytes, and every \`EvidenceCore\` relation with source/provenance/epoch.
- Reapply the same snapshot and require **zero** new records and **no** new
  native transaction. Close BDR; reopen and validate hashes, complete graph,
  record count, and durable sequence equality.
- Write \`report.json\` only after all checks pass. If any check fails,
  leave isolated diagnostic files and emit **no success report**.
- Limit a run to 100,000 records, or a lower operator-selected bound. A
  live writer may append after the snapshot; the proof covers exactly its
  stated snapshot count and hash, not an unbounded moving database.

CI runs the test against a real compiled pinned BDR C ABI v2 library, not a
mock. In addition to source integrity and cold replay, a test leaves the SQLite
WAL writer open while the backup runs, verifies the source file is unchanged
in the no-concurrent-write fixture, and confirms that subsequent writes still
succeed.

## Example for a dedicated, authorized local service account

The following is a **specification**, not a production deploy command.
The actual paths and access must be prepared and approved separately:

\`\`\`bash
PYTHONPATH="/path/to/pinned-memoria/src:/path/to/pinned-bdr" \
BDR_ATOMIC_LIBRARY="/path/to/pinned/libbdr_atomic_c_api.so" \
python scripts/mirror_external_episodes_to_bdr.py \
  --source-sqlite /path/to/live/external-episodes.sqlite3 \
  --output-directory /path/to/new/private/mirror-run \
  --bdr-library /path/to/pinned/libbdr_atomic_c_api.so
\`\`\`

**No direct production cutover is implemented.** A dedicated deployment step
must validate the live-source owner and safe directory, pin executable/library
hashes, hold sufficient disk reserve, run under the existing service identity,
and compare the snapshot count with the live API's count at its capture
boundary. An explicit second reconciliation would be required for episodes
arriving after the snapshot. Preserve the SQLite journal and the Nov local
checkpoint; never delete, reformat or reset them as part of mirror testing.
