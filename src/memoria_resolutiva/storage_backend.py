from __future__ import annotations

import os
import platform
import warnings
from pathlib import Path

from .bdr_store import BDRPolicy, BDRResolutiveMemory, native_bdr_available
from .sqlite_store import SQLiteResolutiveMemory


def preferred_backend() -> str:
    configured = os.environ.get("MEMORIA_STORAGE_BACKEND")
    if configured:
        return configured.strip().lower()
    return "bdr" if platform.system() == "Linux" else "sqlite"


def open_resolutive_memory(
    path: str | Path,
    max_layer: int = 3,
    *,
    backend: str | None = None,
    bdr_policy: BDRPolicy | None = None,
    allow_fallback: bool = True,
):
    selected = (backend or preferred_backend()).lower()
    if selected not in {"bdr", "sqlite", "auto"}:
        raise ValueError(f"unsupported storage backend: {selected}")

    if selected in {"bdr", "auto"}:
        if platform.system() == "Linux" and native_bdr_available():
            return BDRResolutiveMemory(path, max_layer=max_layer, policy=bdr_policy)
        if selected == "bdr" and not allow_fallback:
            raise RuntimeError("BDR requested but native Linux BDR backend is unavailable")
        if selected == "bdr":
            warnings.warn(
                "BDR is the preferred Memoria.ia backend, but this runtime cannot load the "
                "frozen v1.0.0 native backend; falling back to SQLite.",
                RuntimeWarning,
                stacklevel=2,
            )

    sqlite_path = Path(path)
    if sqlite_path.suffix == "":
        sqlite_path.mkdir(parents=True, exist_ok=True)
        sqlite_path = sqlite_path / "memoria.sqlite3"
    else:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteResolutiveMemory(sqlite_path, max_layer=max_layer)
