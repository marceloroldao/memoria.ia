# memoria.ia v0.92 — Repeated persistence and snapshot scaling

Status: stabilization result.

## Zero-drift restart test

A routed/multitrajectory memory with 120 knowledge nodes and 480 routes was subjected to 10 consecutive encode/decode restart cycles. The route signature checked after every restart included:

- knowledge identity;
- active consolidation depth;
- historical consolidation depth.

Observed result: zero state drift across all 10 cycles.

Representative serialized snapshot size: 357,350 bytes.
Mean local encode+decode time in the reconstructed test environment: approximately 22.7 ms per cycle.

## Snapshot scaling

Four-route-per-knowledge workload:

| Knowledge nodes | Routes | Snapshot bytes | Bytes/route |
|---:|---:|---:|---:|
| 100 | 400 | 297,482 | 743.7 |
| 500 | 2,000 | 1,492,440 | 746.2 |
| 1,000 | 4,000 | 2,986,145 | 746.5 |
| 5,000 | 20,000 | 14,987,744 | 749.4 |

Log-log empirical exponent of snapshot size versus route count:

`p ~= 1.002`

This is consistent with approximately linear snapshot growth for this controlled workload.

## Interpretation

The persistence representation does not show evidence of superlinear growth in this range. The next optimization target is therefore the constant factor: approximately 0.74–0.75 KB serialized per route in this JSON snapshot representation.

The JSON format is intentionally transparent and auditable during stabilization; a future compact/binary snapshot may reduce this constant significantly, but should be treated as an implementation optimization rather than a change in memory semantics.

## Limitations

The timing figures are environment-specific. The 5,000-node workload was used for snapshot scaling, not as a claim about production-scale distributed robotics. Payload and trajectory values remain restricted to JSON-serializable values in the v0.91/v0.92 snapshot contract.
