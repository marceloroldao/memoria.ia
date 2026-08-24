from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PATH = _HERE / "two_channel_adversarial_v96.py"
_spec = importlib.util.spec_from_file_location("two_channel_adversarial_v96_sweep", _PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load benchmark: {_PATH}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

for min_state_score in (0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20):
    metrics, _matrix = _mod.evaluate(_mod.build(min_state_score=min_state_score))
    print({"min_state_score": min_state_score, **metrics})
