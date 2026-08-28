from pathlib import Path

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _service(root: Path) -> ConversationSemanticService:
    return ConversationSemanticService(ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True))


def test_offia_vehicle_example_survives_unrelated_turns_and_restart(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    taught = "eu tenho dois carros, um verde e outro azul. o azul é corsa, e o verde um saveiro"
    result = service.ingest(role="user", text=taught, session_id="chat-1", order=1)

    assert result.memory_ids

    for i in range(20):
        service.ingest(role="user", text=f"assunto não relacionado número {i}", session_id="chat-1", order=2 + i)

    direct = service.resolve(query="cor da minha saveiro", session_id="chat-1")
    paraphrase = service.resolve(query="de que cor é a Saveiro?", session_id="chat-1")
    inverse = service.resolve(query="qual é o carro verde?", session_id="chat-1")
    plural = service.resolve(query="qual a cor dos meus carros?", session_id="chat-1")

    assert direct.status == "HIT"
    assert paraphrase.status == "HIT"
    assert inverse.status == "HIT"
    assert plural.status == "HIT"
    assert direct.selected_context == taught
    assert inverse.selected_context == taught
    assert plural.selected_context == taught
    assert direct.memory_ids

    restarted = _service(root)
    again = restarted.resolve(query="cor da minha saveiro", session_id="chat-1")
    assert again.status == "HIT"
    assert again.selected_context == taught


def test_generic_relations_are_not_vehicle_or_color_specific(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    service.ingest(role="user", text="o servidor principal é atlas", session_id="chat")
    service.ingest(role="user", text="o laboratório é norte", session_id="chat")

    atlas = service.resolve(query="qual é o servidor atlas?", session_id="chat")
    norte = service.resolve(query="qual laboratório é norte?", session_id="chat")

    assert atlas.status == "HIT"
    assert norte.status == "HIT"
    assert "atlas" in atlas.selected_context.casefold()
    assert "norte" in norte.selected_context.casefold()


def test_current_relation_update_selects_latest_state(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    service.ingest(role="user", text="minha Saveiro é verde", session_id="chat", order=1)
    service.ingest(role="user", text="minha Saveiro é preta", session_id="chat", order=2)

    current = service.resolve(query="qual a cor da minha Saveiro?", session_id="chat")
    assert current.status == "HIT"
    assert "preta" in current.selected_context.casefold()

    restarted = _service(root)
    again = restarted.resolve(query="de que cor é a Saveiro?", session_id="chat")
    assert again.status == "HIT"
    assert "preta" in again.selected_context.casefold()


def test_ambiguous_relation_abstains(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    service.ingest(role="user", text="meu Corsa é verde", session_id="chat")
    service.ingest(role="user", text="minha Saveiro é verde", session_id="chat")

    result = service.resolve(query="qual é o carro verde?", session_id="chat")
    assert result.status == "UNRESOLVED"
    assert result.memory_ids == ()
    assert result.selected_context == ""


def test_unknown_query_abstains_instead_of_guessing(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    service.ingest(role="user", text="minha Saveiro é verde", session_id="chat")

    result = service.resolve(query="qual a temperatura da garagem?", session_id="chat")
    assert result.status == "UNRESOLVED"
    assert result.confidence == 0.0
    assert result.memory_ids == ()
