# Reproducibility — memoria.ia v0.95.0

Status: stable v0.95 research-release reproducibility manifest.

## Environment

Minimum supported interpreter:

- Python >= 3.10

Create an isolated environment, then install the repository with the declared test dependencies:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

Optional Word2Vec baseline:

```bash
python -m pip install -e '.[word2vec]'
```

To install both test and Word2Vec extras:

```bash
python -m pip install -e '.[test,word2vec]'
```

## Release gate

Run the complete repository test suite through the gate script:

```bash
python scripts/release_gate_v95.py
```

Equivalent explicit test command:

```bash
python -m pytest -q
```

A successful release gate ends with:

```text
v0.95 release gate: PASS
```

The v0.95.0rc1 predecessor completed this gate in a clean Google Colab checkout on Python 3.12 with 267 tests passed and 0 failures. The v0.95.0 promotion changes release metadata/version identifiers only; the functional implementation is frozen from that validated candidate.

## Representative experiments

```bash
python experiments/compact_stress_v63.py
python experiments/scaling_v64.py
python experiments/stability_plasticity_v82.py
python experiments/stochastic_stability_v83.py
python experiments/multitrajectory_v87.py
python experiments/compact_snapshot_v93.py
python experiments/incompressible_snapshot_v94.py
```

Individual assumptions, workloads, metrics and measured results are retained in `docs/results_*.md`.

## Determinism and stochastic experiments

Experiments using stochastic data must use the explicit seeds defined in their scripts/tests. Reported aggregate results should include all configured seeds rather than selecting a favorable run.

## Scientific interpretation

Passing the test suite demonstrates internal implementation consistency and reproducibility of the controlled computational experiments. It does not establish general intelligence, biological equivalence, superiority to neural memory systems, or universal performance guarantees.

Negative and inconclusive results are retained as part of the research record.

## Release traceability

Release version: `0.95.0`

Resolutive Science baseline: `marceloroldao/resolutive-science` v0.1.1

Governance reference: RSPS 1.0-draft

Formal numbered RSMS compatibility is not claimed until a corresponding normative RSMS version is available and audited.
