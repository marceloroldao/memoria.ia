# Research watch: isolated memory experiments

This directory holds small, reproducible regression scenarios motivated by external research. It does not change the product implementation or production data.

## Current baseline (2026-11-16)

`test_memory_lifecycle.py` checks two user-visible invariants: a correction remains current after persistence without leaking across user scopes; a revoked fact cannot resurface through normal or versioned recall after persistence. The historical version remains available only with an explicit audit flag. These are local product-boundary tests, not claims of superiority over another system or of LLM answer quality.

Run from repository root after installing the project test dependencies:

```sh
python -m pytest -q tests/research_watch
```

The existing experimental PR regression runs the full suite on `experiment/*` PR branches. Keep research changes on such branches and use draft PRs; never merge automatically.

## Protocol for future developments

1. Record the primary source URL, publication/change date, the concrete new behavior, and an explicit hypothesis in the PR description.
2. Add a held-out, deterministic scenario with a documented expected outcome, including a negative control when relevant. Avoid training or tuning against its answer.
3. Run the research tests and relevant existing regressions. Report actual pass/fail output, runtime, version/ref, limitations, and any failed cases. Never equate a passing mock test with provider-level validation.
4. Publish only a draft PR from an isolated `experiment/*` branch. Do not alter existing experiments, release workflows, or application code; require a separate review to adopt any change.
5. If no material, testable development appears, do not create a PR or repeat old results.
