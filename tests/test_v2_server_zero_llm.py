from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def _env(data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "MEMORIA_ORGANIZATION_ID": "v2-server-org",
        "MEMORIA_API_KEY": "v2-secret",
        "MEMORIA_DATA_DIR": str(data_dir),
        "MEMORIA_STORAGE_BACKEND": "sqlite",
        "MEMORIA_STORAGE_ALLOW_FALLBACK": "false",
        "MEMORIA_CONVERSATION_RUNTIME": "python",
        "MEMORIA_EPISODIC_RUNTIME": "python",
        "MEMORIA_LLM_PROVIDER": "",
        "MEMORIA_V2_TRAJECTORY_EXPERIMENT": "true",
    })
    env.pop("OPENAI_API_KEY", None)
    env.pop("GEMINI_API_KEY", None)
    return env


def _run(code: str, env: dict[str, str]) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_server_v2_native_resolve_without_llm_survives_restart_and_isolates_sessions(tmp_path: Path):
    data_dir = tmp_path / "server"
    env = _env(data_dir)

    first = _run(
        """
import json
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app

headers = {"X-Memoria-Key": "v2-secret"}

def ingest(client, session_id, text):
    response = client.post(
        "/api/v1/v2/trajectory/ingest",
        headers=headers,
        json={"session_id": session_id, "text": text},
    )
    response.raise_for_status()

def resolve(client, session_id, message):
    response = client.post(
        "/api/v1/resolve/native",
        headers=headers,
        json={"message": message, "scope": {"agent_id": session_id}},
    )
    response.raise_for_status()
    return response.json()

with TestClient(app) as client:
    for text in (
        "meu gato e da cor verde",
        "meu carro e da cor azul",
        "minha camisa e da cor preta",
    ):
        ingest(client, "s1", text)

    for text in (
        "meu gato e da cor verde",
        "meu carro e da cor azul",
        "minha camisa e da cor branca",
    ):
        ingest(client, "s2", text)

    health = client.get("/api/v1/storage/health").json()
    admin = client.get("/api/v1/admin/status", headers=headers).json()
    s1 = resolve(client, "s1", "qual a cor da minha camisa?")
    s2 = resolve(client, "s2", "qual a cor da minha camisa?")
    unknown = resolve(client, "s1", "token completamente inexistente fora")

    print(json.dumps({
        "health": health,
        "llm": admin["llm"],
        "s1": s1,
        "s2": s2,
        "unknown": unknown,
    }, sort_keys=True))
""",
        env,
    )

    assert first["health"]["v2_trajectory_experiment"] is True
    assert first["health"]["v2_trajectory_backend"] == "sqlite"
    assert first["llm"] is None
    assert first["s1"]["status"] == "RESOLVED"
    assert first["s1"]["text"] == "preta"
    assert first["s1"]["external_calls"] == 0
    assert first["s2"]["status"] == "RESOLVED"
    assert first["s2"]["text"] == "branca"
    assert first["s2"]["external_calls"] == 0
    assert first["unknown"]["status"] == "UNRESOLVED"
    assert first["unknown"]["external_calls"] == 0

    restarted = _run(
        """
import json
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app

headers = {"X-Memoria-Key": "v2-secret"}

def resolve(client, session_id):
    response = client.post(
        "/api/v1/resolve/native",
        headers=headers,
        json={
            "message": "qual a cor da minha camisa?",
            "scope": {"agent_id": session_id},
        },
    )
    response.raise_for_status()
    return response.json()

with TestClient(app) as client:
    print(json.dumps({
        "s1": resolve(client, "s1"),
        "s2": resolve(client, "s2"),
        "health": client.get("/api/v1/storage/health").json(),
    }, sort_keys=True))
""",
        env,
    )

    assert restarted["s1"]["status"] == "RESOLVED"
    assert restarted["s1"]["text"] == "preta"
    assert restarted["s1"]["external_calls"] == 0
    assert restarted["s2"]["status"] == "RESOLVED"
    assert restarted["s2"]["text"] == "branca"
    assert restarted["s2"]["external_calls"] == 0
    assert restarted["health"]["v2_trajectory_experiment"] is True


def test_server_keeps_v2_trajectory_routes_disabled_by_default(tmp_path: Path):
    env = _env(tmp_path / "server-default")
    env["MEMORIA_V2_TRAJECTORY_EXPERIMENT"] = "false"

    result = _run(
        """
import json
from fastapi.testclient import TestClient
from memoria_resolutiva.product_server import app

headers = {"X-Memoria-Key": "v2-secret"}
with TestClient(app) as client:
    health = client.get("/api/v1/storage/health").json()
    ingest = client.post(
        "/api/v1/v2/trajectory/ingest",
        headers=headers,
        json={"session_id": "s1", "text": "minha camisa e preta"},
    )
    print(json.dumps({
        "enabled": health["v2_trajectory_experiment"],
        "backend": health["v2_trajectory_backend"],
        "ingest_status": ingest.status_code,
    }, sort_keys=True))
""",
        env,
    )

    assert result["enabled"] is False
    assert result["backend"] is None
    assert result["ingest_status"] == 404
