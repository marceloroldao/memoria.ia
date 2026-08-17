# memoria.ia v0.93 — Compact Snapshot Benchmark

Status: experimental stabilization benchmark.

## Method

Compared the existing JSON envelope snapshot with the v0.93 compact format using the same routed-memory structure at four scales. Each knowledge node had four routes (vision, language, audio, motor), shared one payload, and carried independent route-local lifecycle state. The compact format stores canonical routed JSON compressed with zlib level 9 under a binary header with format version, raw length, and CRC32.

Important limitation: the corpus is structured and repetitive, so compression ratio is expected to be unusually strong. These numbers should not be generalized to arbitrary payload distributions.

## Results

| knowledge | routes | JSON bytes | compact bytes | reduction | JSON bytes/route | compact bytes/route | JSON encode ms | compact encode ms | compact raw-decode ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 400 | 302,057 | 4,317 | 98.57% | 755.14 | 10.79 | 7.76 | 7.55 | 2.41 |
| 500 | 2,000 | 1,514,464 | 19,720 | 98.70% | 757.23 | 9.86 | 87.71 | 28.84 | 11.45 |
| 1,000 | 4,000 | 3,029,976 | 38,519 | 98.73% | 757.49 | 9.63 | 71.21 | 55.94 | 27.57 |
| 5,000 | 20,000 | 15,198,067 | 180,519 | 98.81% | 759.90 | 9.03 | 373.43 | 426.04 | 162.79 |

## Interpretation

The compact format removes most of the textual repetition in route state. At the largest tested scale, snapshot size falls from about 15.2 MB to about 180 KB in this corpus.

The tradeoff is CPU cost. At 20,000 routes, compact encoding was slightly slower than the verbose JSON envelope (about 426 ms versus 373 ms), while decompression plus JSON parsing of the raw routed payload took about 163 ms.

Therefore v0.93 should be viewed as a storage/transfer optimization, not a free speed optimization.

## Integrity

The v0.93 format retains explicit versioning, uncompressed-length validation, CRC32 verification, and reuses the v0.91 routed decoder semantics after decompression. Corruption tests reject modified payloads rather than silently restoring damaged state.

## Decision

Keep both formats:

- verbose JSON envelope: audit/debug/reference format;
- compact MI93: storage and transfer candidate.

Before v0.95, run an integrated v0.94 audit with less-compressible/randomized payloads so the release record includes both favorable and adversarial compression cases.