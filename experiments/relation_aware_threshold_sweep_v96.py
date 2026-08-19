from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PATH = _HERE / "relation_aware_adversarial_v96.py"
_spec = importlib.util.spec_from_file_location("relation_aware_adversarial_v96_sweep", _PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load benchmark: {_PATH}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

for threshold in (0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12):
    metrics, _ = _mod.evaluate(threshold, verbose=False)
    print(metrics)
