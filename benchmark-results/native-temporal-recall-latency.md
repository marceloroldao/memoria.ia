# Native temporal recall latency

The baseline is `2e23b4a2f8306f079a38003536d3abbda6a4d8b6`. The candidate defers semantic source and lineage preparation until the query reaches semantic recall. Both libraries were built in Release mode with GCC 14.2.0 on Linux x86-64 (AMD EPYC 9V74), using Resolutive-DB `317882a00f041fc1568ff986af8016b09453f21a`.

The [benchmark](../benchmarks/benchmark_native_temporal_recall.py) uses the native Python adapter with a reopened, warmed BDR. Each synthetic history has five observations about the target and fills the remaining records with other entities in the same session. The script alternates execution order between builds, checks equality of the complete responses, and records 18 timings per build and query at each size. The reported medians include adapter and native query time. Ingestion, database opening, HTTP, and Android are outside the measurement.

| Records | Query | Baseline median (ms) | Candidate median (ms) | Speedup |
| ---: | --- | ---: | ---: | ---: |
| 128 | Snapshot | 0.239 | 0.081 | 2.96× |
| 128 | Comparison | 0.318 | 0.159 | 2.00× |
| 128 | Timeline | 0.346 | 0.182 | 1.90× |
| 512 | Snapshot | 2.648 | 0.239 | 11.09× |
| 512 | Comparison | 2.898 | 0.482 | 6.01× |
| 512 | Timeline | 3.023 | 0.605 | 5.00× |
| 2,048 | Snapshot | 53.336 | 0.878 | 60.75× |
| 2,048 | Comparison | 55.306 | 1.825 | 30.31× |
| 2,048 | Timeline | 54.900 | 2.313 | 23.74× |

The validation run passed 39 native tests and 22 Python integration tests. The integration tests include 426 temporal queries checked against an independent reference. The legacy benchmark recorded 27 of 28 correct responses, with the known abstention for the delivery date versus arrival. The inverse-arrival temporal benchmark passed all 16 cases.
