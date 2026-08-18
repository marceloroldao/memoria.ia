# v0.96 Candidate-Limit Sensitivity

This note records the controlled sensitivity experiment for `DiscriminativeSemanticRouterV96`.

## Setup

- 1000 registered concepts;
- 200 held-out synonym-style queries;
- exact semantic scoring unchanged;
- only the number of preselected candidates varies;
- full scan used as reference.

## Controlled result

In equivalent local execution, candidate limits of 8, 16, 32 and 64 all retained 100% accuracy and 100% parity with the full scan on this synthetic corpus.

Observed approximate timings from the equivalent local run:

| candidate_limit | accuracy | parity | mean candidates | ms/query | speedup vs full |
|---:|---:|---:|---:|---:|---:|
| 8 | 1.00 | 1.00 | 8 | 1.98 | 4.44x |
| 16 | 1.00 | 1.00 | 16 | 2.03 | 4.34x |
| 32 | 1.00 | 1.00 | 32 | 2.17 | 4.05x |
| 64 | 1.00 | 1.00 | 64 | 2.47 | 3.56x |

The full scan reference was about 8.81 ms/query in the same equivalent local run.

## Interpretation

Within this controlled corpus, `candidate_limit=8` is the best tested operating point: it preserves the reference decision while minimizing exact scoring work.

This is **not** promoted as a production default yet. The result may fail when concepts are semantically close, contextual discriminators are noisy, or multiple concepts share rare features. Before promotion, v0.96 must test:

1. near-neighbor concepts;
2. corrupted/missing contextual features;
3. adversarial overlap;
4. recall under candidate pressure;
5. repeated-run latency.

The published v0.95.1 baseline remains unchanged.
