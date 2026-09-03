from pathlib import Path

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _service(root: Path) -> ConversationSemanticService:
    return ConversationSemanticService(ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True))


def test_original_user_fact_beats_repeated_assistant_echo(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    user = service.ingest(role="user", text="a caixa vermelha tem o multímetro e o código é 4729", session_id="s", order=1)
    source_id = user.memory_ids[0]
    for i in range(5):
        service.ingest(role="assistant", text="o código da caixa com o multímetro é 4729", session_id="s", order=2 + i, parent_memory_ids=(source_id,))

    result = service.resolve(query="qual é o código da caixa que tem o multímetro?", session_id="s")
    assert result.status == "HIT"
    assert result.provenance
    assert result.provenance[0]["source_type"] in {"user_assertion", "derived_relation"}
    assert result.provenance[0]["source_type"] != "assistant_generated"


def test_user_correction_supersedes_wrong_assistant_answer(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    wrong = service.ingest(role="assistant", text="o código da caixa é 1111", session_id="s", order=1)
    correction = service.ingest(role="user", text="correção: o código da caixa é 4729", session_id="s", order=2, corrects_memory_ids=(wrong.memory_ids[0],))
    result = service.resolve(query="qual é o código da caixa?", session_id="s")
    assert result.status == "HIT"
    assert "4729" in result.selected_context
    assert result.provenance[0]["source_type"] in {"user_correction", "derived_relation"}
    assert service.provenance.inspect(wrong.memory_ids[0], namespace="s").superseded_by == correction.memory_ids[0]


def test_user_correction_supersedes_prior_user_fact_and_survives_restart(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    old = service.ingest(role="user", text="device alpha mode is standby", session_id="s", order=1)
    correction = service.ingest(
        role="user",
        text="device alpha mode is active",
        session_id="s",
        order=2,
        corrects_memory_ids=(old.memory_ids[0],),
    )

    result = service.resolve(query="device alpha mode", session_id="s")
    assert result.status == "HIT"
    assert result.selected_context == "device alpha mode is active"
    assert service.provenance.inspect(old.memory_ids[0], namespace="s").superseded_by == correction.memory_ids[0]

    restarted = _service(root)
    after = restarted.resolve(query="device alpha mode", session_id="s")
    assert after.status == "HIT"
    assert after.selected_context == "device alpha mode is active"


def test_generated_only_memory_is_preserved_but_not_factual_authority(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    stored = service.ingest(role="assistant", text="a previsão interna é 17 unidades", session_id="s", order=1)
    result = service.resolve(query="qual é a previsão interna?", session_id="s")
    assert result.status == "UNRESOLVED"
    meta = service.provenance.inspect(stored.memory_ids[0], namespace="s")
    assert meta.source_type == "assistant_generated"
    assert meta.authority < 0.5


def test_provenance_survives_restart(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    stored = service.ingest(role="user", text="o servidor Atlas fica no laboratório Norte", session_id="s", order=3, timestamp="2026-08-28T12:00:00Z")
    before = service.resolve(query="onde fica o servidor Atlas?", session_id="s")
    restarted = _service(root)
    after = restarted.resolve(query="onde fica o servidor Atlas?", session_id="s")
    assert after.status == before.status == "HIT"
    assert after.memory_ids == before.memory_ids
    assert after.provenance == before.provenance
    meta = restarted.provenance.inspect(stored.memory_ids[0], namespace="s")
    assert meta.source_type == "user_assertion"
    assert meta.created_order == 3
    assert meta.created_time == "2026-08-28T12:00:00Z"
