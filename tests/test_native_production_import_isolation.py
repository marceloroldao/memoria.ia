from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REFERENCE_MODULES = (
    "memoria_resolutiva.product_conversation",
    "memoria_resolutiva.product_episodic",
    "memoria_resolutiva.reference_conversation",
    "memoria_resolutiva.reference_episodic",
    "memoria_resolutiva.memory_provenance",
)


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; import isolation runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _base_env(data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "MEMORIA_ORGANIZATION_ID": "native-import-isolation-org",
        "MEMORIA_API_KEY": "native-import-isolation-secret",
        "MEMORIA_DATA_DIR": str(data_dir),
        "MEMORIA_LLM_PROVIDER": "",
        "MEMORIA_STORAGE_BACKEND": "sqlite",
        "MEMORIA_STORAGE_ALLOW_FALLBACK": "false",
    })
    env.pop("MEMORIA_CONVERSATION_RUNTIME", None)
    env.pop("MEMORIA_EPISODIC_RUNTIME", None)
    return env


def _probe(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    code = f"""
import json
import sys
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app
blocked = {REFERENCE_MODULES!r}
with TestClient(app) as client:
    response = client.get('/api/v1/storage/health')
    response.raise_for_status()
    print(json.dumps({{
        'health': response.json(),
        'loaded_reference_modules': [name for name in blocked if name in sys.modules],
    }}, sort_keys=True))
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_native_production_startup_does_not_import_python_reference_semantics(tmp_path: Path):
    env = _base_env(tmp_path / "native")
    env["MEMORIA_NATIVE_LIB"] = str(_native_library())
    result = _probe(env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["health"]["conversation_runtime"] == "native"
    assert payload["health"]["episodic_runtime"] == "native"
    assert payload["loaded_reference_modules"] == []


def test_explicit_python_mode_loads_reference_implementations(tmp_path: Path):
    env = _base_env(tmp_path / "python")
    env["MEMORIA_CONVERSATION_RUNTIME"] = "python"
    env["MEMORIA_EPISODIC_RUNTIME"] = "python"
    env.pop("MEMORIA_NATIVE_LIB", None)
    result = _probe(env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["health"]["conversation_runtime"] == "python"
    assert payload["health"]["episodic_runtime"] == "python"
    loaded = set(payload["loaded_reference_modules"])
    assert "memoria_resolutiva.reference_conversation" in loaded
    assert "memoria_resolutiva.reference_episodic" in loaded
    assert "memoria_resolutiva.product_conversation" in loaded
    assert "memoria_resolutiva.product_episodic" in loaded
