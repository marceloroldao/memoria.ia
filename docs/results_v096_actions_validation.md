# v0.96 GitHub Actions validation

Validation workflow: `.github/workflows/v096-validation.yml`

Validated on GitHub-hosted Ubuntu 24.04 with Python 3.12.

## Workflow result

Run `32213607601` completed successfully.

### Test suite

- Full project suite: **299 passed**.
- Trajectory contrastive unit tests: **3 passed**.

### Trajectory contrastive benchmark

At the reference threshold `0.14`:

- accuracy: **0.9375**
- known recall: **0.9166666667**
- open-set false-positive rate: **0.0**
- wrong-known-class rate: **0.0**
- known abstention rate: **0.0833333333**

The two abstentions were `billing_fee` and `network_outage`, both with positive scores around `0.121-0.123`, below the positive threshold.

### Threshold sweep

Thresholds `0.10`, `0.11`, and `0.12` all produced:

- accuracy: **1.0**
- known recall: **1.0**
- open-set false-positive rate: **0.0**
- wrong-known-class rate: **0.0**
- known abstention rate: **0.0**

Thresholds `0.125` through `0.14` produced accuracy `0.9375` and known recall `0.9167`, while retaining zero open-set false positives and zero wrong-known-class predictions.

## Current experimental operating point

`threshold = 0.12` is the strongest current project-controlled operating point because it is the most conservative tested threshold that retained perfect performance on this benchmark.

This is not yet a production default. Additional independently constructed noisy/open-set corpora are required before promotion.
