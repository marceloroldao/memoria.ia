from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_persistence import ProductSnapshotPersistence, PersistentEnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


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
    semantic = client.get('/api/v1/semantic/relations/health', headers={'X-Memoria-Key': 'native-default-secret'})
    print(json.dumps({
        'storage': response.json(),
        'semantic_status': semantic.status_code,
        'semantic_body': semantic.json() if semantic.status_code == 200 else None,
    }, sort_keys=True))
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
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    health = probe["storage"]
    assert health["conversation_runtime"] == "native"
    assert health["episodic_runtime"] == "native"
    assert health["automatic_semantic_consolidation"] is True
    assert health["automatic_concept_resolution"] is True
    assert health["native_concept_catalog_materialized"] is True
    assert health["concept_namespace"] == "semantic"
    assert health["concept_relation_traversal"] is False
    assert probe["semantic_status"] == 404


def test_native_server_materializes_persisted_concept_and_resolves_alias(tmp_path: Path):
    library = _native_library()
    data_dir = tmp_path / "concept-e2e"
    persistence = ProductSnapshotPersistence(
        data_dir / "persistence",
        backend="sqlite",
        allow_fallback=False,
    )
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("native-default-org"),
        persistence=persistence,
    )
    concepts = PersistentSemanticConceptStore(service)
    concepts.register_concept(
        MemoryScope("native-default-org"),
        "voltage",
        aliases=("ddp",),
        namespace="semantic",
        sense_key="electric",
        concept_id="concept:voltage",
        context_cues=("circuit",),
    )
    service.save(data_dir)

    env = _base_env(data_dir)
    env["MEMORIA_NATIVE_LIB"] = str(library)
    env["MEMORIA_CONCEPT_NAMESPACE"] = "semantic"
    code = """
import json
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app
headers = {'X-Memoria-Key': 'native-default-secret'}
with TestClient(app) as client:
    health = client.get('/api/v1/storage/health').json()
    ingest = client.post('/api/v1/conversation/ingest', headers=headers, json={
        'role': 'user', 'text': 'voltage', 'session_id': 'session-e2e'
    })
    resolve = client.post('/api/v1/conversation/resolve', headers=headers, json={
        'query': 'ddp', 'session_id': 'session-e2e'
    })
    print(json.dumps({
        'health': health,
        'ingest_status': ingest.status_code,
        'ingest': ingest.json(),
        'resolve_status': resolve.status_code,
        'resolve': resolve.json(),
    }, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    assert probe["health"]["native_concept_catalog_materialized"] is True
    assert probe["health"]["native_concept_catalog_count"] == 1
    assert probe["health"]["automatic_concept_resolution"] is True
    assert probe["ingest_status"] == 200
    assert probe["resolve_status"] == 200
    assert probe["resolve"]["status"] == "HIT"
    assert "voltage" in probe["resolve"]["selected_context"]


def test_explicit_python_reference_mode_does_not_require_native_library(tmp_path: Path):
    env = _base_env(tmp_path / "python")
    env["MEMORIA_CONVERSATION_RUNTIME"] = "python"
    env["MEMORIA_EPISODIC_RUNTIME"] = "python"
    env.pop("MEMORIA_NATIVE_LIB", None)
    result = _health_probe(env)
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    health = probe["storage"]
    assert health["conversation_runtime"] == "python"
    assert health["episodic_runtime"] == "python"
    assert health["automatic_semantic_consolidation"] is True
    assert health["automatic_concept_resolution"] is True
    assert health["concept_relation_traversal"] is True
    assert probe["semantic_status"] == 200
    assert probe["semantic_body"]["capability"] == "concept-relation-traversal-v1"


def test_native_default_fails_closed_when_library_is_missing(tmp_path: Path):
    env = _base_env(tmp_path / "missing")
    env.pop("MEMORIA_NATIVE_LIB", None)
    result = _health_probe(env)
    assert result.returncode != 0
    assert "MEMORIA_NATIVE_LIB is required" in result.stderr
