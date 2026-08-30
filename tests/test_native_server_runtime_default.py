from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; native server default runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _base_env(data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "MEMORIA_ORGANIZATION_ID": "native-default-org",
        "MEMORIA_API_KEY": "native-default-secret",
        "MEMORIA_DATA_DIR": str(data_dir),
        "MEMORIA_LLM_PROVIDER": "",
        "MEMORIA_STORAGE_BACKEND": "sqlite",
        "MEMORIA_STORAGE_ALLOW_FALLBACK": "false",
    })
    env.pop("MEMORIA_CONVERSATION_RUNTIME", None)
    env.pop("MEMORIA_EPISODIC_RUNTIME", None)
    return env


def _health_probe(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    code = """
import json
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app
with TestClient(app) as client:
    response = client.get('/api/v1/storage/health')
    response.raise_for_status()
    print(json.dumps(response.json(), sort_keys=True))
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_server_defaults_to_native_when_runtime_overrides_are_absent(tmp_path: Path):
    library = _native_library()
    env = _base_env(tmp_path / "native")
    env["MEMORIA_NATIVE_LIB"] = str(library)
    result = _health_probe(env)
    assert result.returncode == 0, result.stderr
    health = json.loads(result.stdout.strip().splitlines()[-1])
    assert health["conversation_runtime"] == "native"
    assert health["episodic_runtime"] == "native"


def test_explicit_python_reference_mode_does_not_require_native_library(tmp_path: Path):
    env = _base_env(tmp_path / "python")
    env["MEMORIA_CONVERSATION_RUNTIME"] = "python"
    env["MEMORIA_EPISODIC_RUNTIME"] = "python"
    env.pop("MEMORIA_NATIVE_LIB", None)
    result = _health_probe(env)
    assert result.returncode == 0, result.stderr
    health = json.loads(result.stdout.strip().splitlines()[-1])
    assert health["conversation_runtime"] == "python"
    assert health["episodic_runtime"] == "python"


def test_native_default_fails_closed_when_library_is_missing(tmp_path: Path):
    env = _base_env(tmp_path / "missing")
    env.pop("MEMORIA_NATIVE_LIB", None)
    result = _health_probe(env)
    assert result.returncode != 0
    assert "MEMORIA_NATIVE_LIB is required" in result.stderr
