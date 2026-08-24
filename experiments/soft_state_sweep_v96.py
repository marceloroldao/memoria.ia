from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BENCH = _HERE / "soft_state_adversarial_v96.py"
_spec = importlib.util.spec_from_file_location("soft_state_adversarial_v96_sweep", _BENCH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load: {_BENCH}")
_bench = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _bench
_spec.loader.exec_module(_bench)


def main() -> None:
    for evidence in (1, 2):
        for sim in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
            router = _bench.build(
                min_soft_similarity=sim,
                min_total_state_evidence=evidence,
            )
            metrics = _bench.evaluate(router, verbose=False)
            print({
                "min_total_state_evidence": evidence,
                "min_soft_similarity": sim,
                **metrics,
            })


if __name__ == "__main__":
    main()
