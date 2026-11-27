# Native temporal session cache

The cache keeps parsed observations for each queried session in memory. It reads original text from persisted BDR turns and parses only new matching turns on later queries. A reopened handle reconstructs the cache on demand. The persisted schema and the temporal conflict rules are the same as in the baseline.

## Release benchmark

The baseline is `24071fd03c1124a9c27d66962c0601716b2261d9`. Both builds use GCC 14.2.0 on Linux x86-64 (AMD EPYC 9V74) and Resolutive-DB `317882a00f041fc1568ff986af8016b09453f21a`.

The [benchmark](../benchmarks/benchmark_native_temporal_recall.py) writes each synthetic history using the baseline, then opens the same BDR with both builds in alternating order. The benchmark checks equality of the complete adapter responses. It times four initial snapshots and 36 repeated queries per route and build. The measurements cover the native Python adapter and the query itself. They exclude BDR opening, ingestion, HTTP, and Android.

```sh
export PYTHONPATH=src
for sessions in 1 64; do
    python benchmarks/benchmark_native_temporal_recall.py \
        --baseline /path/to/baseline.so --candidate /path/to/candidate.so \
        --sizes 2048 8192 --sessions "$sessions"
done
```

| Total records | Sessions | Query | Baseline median (ms) | Cache median (ms) |
| ---: | ---: | --- | ---: | ---: |
| 2,048 | 1 | Snapshot | 0.872 | 0.100 |
| 2,048 | 1 | Comparison | 1.848 | 0.170 |
| 2,048 | 1 | Timeline | 2.355 | 0.213 |
| 2,048 | 1 | First snapshot | 1.037 | 2.456 |
| 8,192 | 1 | Snapshot | 3.524 | 0.347 |
| 8,192 | 1 | Comparison | 7.329 | 0.576 |
| 8,192 | 1 | Timeline | 9.240 | 0.720 |
| 8,192 | 1 | First snapshot | 3.646 | 9.139 |
| 2,048 | 64 | Snapshot | 0.060 | 0.032 |
| 2,048 | 64 | Comparison | 0.093 | 0.043 |
| 2,048 | 64 | Timeline | 0.111 | 0.052 |
| 2,048 | 64 | First snapshot | 0.203 | 0.195 |
| 8,192 | 64 | Snapshot | 0.185 | 0.080 |
| 8,192 | 64 | Comparison | 0.242 | 0.052 |
| 8,192 | 64 | Timeline | 0.291 | 0.058 |
| 8,192 | 64 | First snapshot | 0.495 | 0.565 |

The 64-session workload distributes filler records across 64 sessions and queries one of them. A first query still examines the persisted turns to identify the requested session and parses its observations, including those after a snapshot's cutoff. The cache adds resident memory for parsed observations. With 8,192 cached observations in one session, the observation array occupies approximately 1.9 MiB on this build, excluding allocator overhead and temporary query state.

## Validation

All 39 native tests and all 22 selected integration tests passed. The integration tests include 426 temporal queries checked against an independent reference and a test with 25 sessions covering live writes, explicit corrections, historical reads, and logical format. A legacy 28-query workload reopened from a BDR written by the baseline scored 27 correct responses, with the known delivery-versus-arrival abstention. All 16 temporal queries in the legacy workload also passed when events arrived in reverse order.
