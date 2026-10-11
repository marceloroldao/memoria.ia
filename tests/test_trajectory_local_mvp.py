"""Real HTTP/native MVP contracts, including negative evidence and cold restore."""
import os
from pathlib import Path
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from trajectory_local_mvp import create_app
from trajectory_copy_relation_probe import fixture
from trajectory_window_consistency_probe import window_snapshot

HEADERS = {"X-Memoria-Key": "test-secret"}


@pytest.fixture
def app_factory(tmp_path):
    configured = os.environ.get("MEMORIA_NATIVE_LIBRARY")
    if not configured:
        pytest.skip("requires native BDR library")
    library = Path(configured).resolve()
    assert library.is_file()

    def factory(directory=None):
        return create_app(library=library, data_dir=directory or tmp_path / "state", api_key="test-secret")
    return factory


def add(client, text, scope="principal", kind="user_turn"):
    response = client.post("/api/entries", headers=HEADERS, json=dict(
        text=text, scope=scope, source_kind=kind))
    assert response.status_code == 201, response.text
    assert response.json()["persisted"] is True
    return response.json()["entry"]


def query(client, text, scope="principal", experimental=False):
    response = client.post("/api/query", headers=HEADERS, json=dict(
        text=text, scope=scope, experimental=experimental))
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["answer"] is None and value["qualified"] is False
    assert value["selected_target"] is None and value["selection_used"] is False
    assert value["query_recorded"] is False
    return value


def entries(client, scope="principal"):
    response = client.get("/api/entries", params={"scope": scope}, headers=HEADERS)
    assert response.status_code == 200
    return response.json()


def test_real_question_preserves_competing_contents_origins_and_read_only_query(app_factory):
    with TestClient(app_factory()) as c:
        a = add(c, "Meu gato se chama Alt.")
        b = add(c, "Meu gato se chama Bia.")
        copies = [add(c, a["text"]) for _ in range(4)]
        add(c, "Meu gato dorme no sofa.")
        add(c, "Meu cachorro se chama Bolt.", scope="outra")
        generated = add(c, a["text"], kind="assistant_generated")
        before = entries(c)
        result = query(c, "Qual nome do meu gato?")
        by_text = {r["text"]: r for r in result["candidates"]}
        assert {a["text"], b["text"]} <= set(by_text)
        assert "Meu cachorro se chama Bolt." not in by_text
        assert {o["source_id"] for o in by_text[a["text"]]["origins"]} == {a["source_id"], *(r["source_id"] for r in copies)}
        assert generated["source_id"] not in str(result)
        assert entries(c) == before
        assert query(c, "zzzzzzz")["status"] == "UNRESOLVED"
        assert entries(c) == before


def test_generated_only_and_foreign_only_never_supply_local_content(app_factory):
    with TestClient(app_factory()) as c:
        add(c, "Meu gato se chama Alt.", kind="assistant_generated")
        add(c, "Meu gato se chama Bia.", scope="outra")
        result = query(c, "Meu gato se chama Alt.", experimental=True)
        assert result["candidates"] == []
        route = result["experimental"]["routes"]["positive_copy_witness"]
        assert route["proposal_payload_id"] is None
        assert route["episodes"] == []


def test_generated_storage_does_not_train_or_change_user_recall_field(app_factory):
    app = app_factory()
    with TestClient(app) as c:
        add(c, "Meu gato se chama Alt.")
        before = window_snapshot(app.state.native, "conversation:mvp:principal")
        result = query(c, "Qual nome do meu gato?")
        for text in ("Meu gato se chama Bia.", "Meu gato se chama Alt.", "Meu gato é azul."):
            row = add(c, text, kind="assistant_generated")
            assert row["hierarchy_id"] == "conversation:mvp:principal:generated"
        assert window_snapshot(app.state.native, "conversation:mvp:principal") == before
        assert query(c, "Qual nome do meu gato?")["candidates"] == result["candidates"]
        assert len(entries(c)["entries"]) == 4


def test_cold_restart_and_closed_backup_restore_preserve_full_view(app_factory, tmp_path):
    with TestClient(app_factory()) as c:
        first = add(c, "Meu gato se chama Alt.")
        add(c, "Meu gato se chama Bia.")
        before = entries(c)
        warm = query(c, "Qual nome do meu gato?")
    backup = tmp_path / "restored"
    shutil.copytree(tmp_path / "state", backup)
    with TestClient(app_factory()) as c:
        assert entries(c) == before
        assert query(c, "Qual nome do meu gato?") == warm
        next_entry = add(c, "Meu gato dorme no sofa.")
        assert next_entry["sequence"] == 3
        assert next_entry["source_id"] != first["source_id"]
    with TestClient(app_factory(backup)) as c:
        assert entries(c) == before
        assert query(c, "Qual nome do meu gato?") == warm


@pytest.mark.parametrize("case", ["matched_context", "same_context_rival", "generated_barrier", "multiple_targets"])
def test_experimental_routes_use_persisted_inputs_and_keep_abstentions(app_factory, case):
    rows, original_region, text, _ = fixture(20261219, case)
    with TestClient(app_factory()) as c:
        for row in rows:
            add(c, row["text"], scope="principal" if row["hierarchy_id"] == original_region else "outra", kind=row["source_kind"])
        before = entries(c)
        result = query(c, text, experimental=True)
        route = result["experimental"]["routes"]["positive_copy_witness"]
        assert (route["proposal_payload_id"] is not None) == (case == "matched_context")
        assert route["answer"] is None and route["qualified"] is False
        assert result["experimental"]["unknown_cuts"]
        assert entries(c) == before
        for e in route["episodes"]:
            for relation in e["inferred_relations"]:
                assert relation["observed_reply_to"] is False
                assert any([r["hierarchy_id"], r["source_id"], r["sequence"]] == relation["origin"] for r in before["entries"])


def test_auth_validation_and_explicit_experiment_bound_do_not_write(app_factory):
    with TestClient(app_factory()) as c:
        assert c.get("/").status_code == 200
        for path in ("/api/entries", "/api/query"):
            assert c.post(path, json={"text": "hello"}).status_code == 401
        assert c.get("/api/entries").status_code == 401
        for body in ({"text": "   "}, {"text": "x", "scope": "../other"},
                     {"text": "x", "source_kind": "untrusted"}, {"text": "x" * 20001}):
            assert c.post("/api/entries", headers=HEADERS, json=body).status_code == 422
        assert entries(c)["entries"] == []
        add(c, "a" * 4097)
        before = entries(c)
        assert c.post("/api/query", headers=HEADERS, json={"text": "a", "experimental": True}).status_code == 413
        assert entries(c) == before
        assert query(c, "zzzzzzz")["status"] == "UNRESOLVED"


def test_single_directory_writer_and_concurrent_source_allocation(app_factory):
    with TestClient(app_factory()) as c:
        with pytest.raises(BlockingIOError):
            with TestClient(app_factory()):
                pass
        with ThreadPoolExecutor(max_workers=4) as pool:
            recorded = list(pool.map(lambda i: add(c, f"entry {i}"), range(8)))
        assert sorted(r["sequence"] for r in recorded) == list(range(1, 9))
        assert len({r["source_id"] for r in recorded}) == 8
        assert len(entries(c)["entries"]) == 8


def test_between_call_write_rejects_query_instead_of_returning_stale_view(app_factory):
    app = app_factory()
    with TestClient(app) as c:
        add(c, "Meu gato se chama Alt.")
        native = app.state.native

        class Interleaved:
            def call(self, name, payload):
                result = native.call(name, payload)
                if name == "resolve_structural_text":
                    status, _ = native.call("observe_structural_text", dict(
                        hierarchy_id="conversation:mvp:principal", source_id="external-test",
                        sequence=2, text="Meu gato se chama Bia.", source_kind="user_turn"))
                    assert status == 0
                return result
        app.state.native = Interleaved()
        response = c.post("/api/query", headers=HEADERS, json={"text": "Qual nome do meu gato?"})
        app.state.native = native
        assert response.status_code == 409
        assert "candidates" not in response.json()
        assert len(entries(c)["entries"]) == 2


def test_structural_scores_are_diagnostics_not_factual_confidence(app_factory):
    with TestClient(app_factory()) as c:
        add(c, "Meu gato se chama Alt.")
        result = query(c, "Qual nome do meu gato?")
        candidate = result["candidates"][0]
        assert candidate["native_support"]["exact_overlap"] >= 2
        assert candidate["support_is_factual_confidence"] is False
        assert result["retrieval"]["limit_may_have_hidden_alternatives"] is False
        assert result["retrieval"]["all_relevant_content_recovered"] is None


def test_native_recall_limit_warns_without_claiming_complete_conflict_detection(app_factory):
    with TestClient(app_factory()) as c:
        for i in range(20):
            add(c, f"Meu gato se chama Nome{i}.")
        before = entries(c)
        result = query(c, "Qual nome do meu gato?")
        assert len(result["candidates"]) == 16
        assert result["retrieval"]["native_context_count"] == 16
        assert result["retrieval"]["limit_may_have_hidden_alternatives"] is True
        assert result["retrieval"]["all_relevant_content_recovered"] is None
        assert entries(c) == before
