from pathlib import Path

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _service(root: Path) -> ConversationSemanticService:
    return ConversationSemanticService(ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True))


def test_offia_vehicle_relations_survive_unrelated_turns_and_restart(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    taught = "eu tenho dois carros, um verde e outro azul. o azul é corsa, é o verde um saveiro"
    result = service.ingest(role="user", text=taught, session_id="chat-1", order=1)

    assert result.unresolved is False
    assert len(result.memory_ids) >= 4

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
    assert any(r["subject"].casefold() == "saveiro" and r["object"].casefold() == "verde" for r in direct.relations)
    assert any(r["subject"].casefold() == "saveiro" for r in inverse.relations)
    assert {r["subject"].casefold() for r in plural.relations if r["predicate"] == "has_color"} == {"corsa", "saveiro"}
    assert direct.memory_ids
    assert direct.selected_context == taught

    restarted = _service(root)
    again = restarted.resolve(query="cor da minha saveiro", session_id="chat-1")
    assert again.status == "HIT"
    assert again.selected_context == taught
    assert again.memory_ids == direct.memory_ids


def test_same_attribute_does_not_cross_contaminate_entities(tmp_path: Path):
    service = _service(tmp_path / "evidence")
    service.ingest(role="user", text="minha Saveiro é verde", session_id="chat")
    service.ingest(role="user", text="meu Corsa é azul", session_id="chat")

    saveiro = service.resolve(query="cor da minha Saveiro", session_id="chat")
    corsa = service.resolve(query="de que cor é o Corsa?", session_id="chat")

    assert saveiro.status == "HIT"
    assert corsa.status == "HIT"
    assert {r["object"].casefold() for r in saveiro.relations if r["predicate"] == "has_color"} == {"verde"}
    assert {r["object"].casefold() for r in corsa.relations if r["predicate"] == "has_color"} == {"azul"}


def test_color_update_selects_current_state_and_keeps_persistence(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    service.ingest(role="user", text="minha Saveiro é verde", session_id="chat", order=1)
    service.ingest(role="user", text="minha Saveiro é preta", session_id="chat", order=2)

    current = service.resolve(query="qual a cor da minha Saveiro?", session_id="chat")
    assert current.status == "HIT"
    assert {r["object"].casefold() for r in current.relations if r["predicate"] == "has_color"} == {"preta"}
    assert "preta" in current.selected_context.casefold()

    restarted = _service(root)
    again = restarted.resolve(query="de que cor é a Saveiro?", session_id="chat")
    assert again.status == "HIT"
    assert {r["object"].casefold() for r in again.relations if r["predicate"] == "has_color"} == {"preta"}


def test_ambiguous_inverse_query_abstains(tmp_path: Path):
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
