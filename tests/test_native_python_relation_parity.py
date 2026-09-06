from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.relational_activation import activate


VECTORS = (
    ("meu servidor é um atlas", (("servidor", "is", "atlas", 0.95),)),
    ("Minha bateria = carregada", (("bateria", "is", "carregada", 0.95),)),
    (
        "meu carro é um sedan e o motor um v8",
        (("carro", "is", "sedan", 0.95), ("motor", "is", "v8", 0.85)),
    ),
    (
        "o alpha é um nodo; o beta um espelho",
        (("alpha", "is", "nodo", 0.95), ("beta", "is", "espelho", 0.85)),
    ),
    ("sensor = active; sensor = active", (("sensor", "is", "active", 0.95),)),
    ("o outro é ativo", ()),
    ("isso é verdade", ()),
    ("isto é importante", ()),
    ("aquilo é estranho", ()),
    ("ele é azul", ()),
    ("ela é engenheira", ()),
    ("aqui é frio", ()),
    ("quem é atlas", ()),
    ("onde é norte", ()),
    ("como é azul", ()),
)


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; relation parity runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _python_service(root: Path) -> ConversationSemanticService:
    evidence = ProductEvidenceService.open(root / "python-evidence", backend="sqlite", allow_fallback=False)
    return ConversationSemanticService(evidence)


def _native_service(root: Path, library: Path) -> NativeConversationService:
    return NativeConversationService(
        library_path=library,
        data_dir=root / "native-state",
        organization_id="relation-parity-org",
    )


def _contract(result) -> tuple[tuple[str, str, str, float], ...]:
    return tuple(
        (
            str(row["subject"]),
            str(row["predicate"]),
            str(row["object"]),
            round(float(row["confidence"]), 6),
        )
        for row in result.relations
    )


def test_python_and_native_share_product_relation_vectors(tmp_path: Path):
    python_service = _python_service(tmp_path)
    native_service = _native_service(tmp_path, _native_library())
    try:
        for order, (text, expected) in enumerate(VECTORS, start=1):
            session_id = f"vector-{order}"
            python_result = python_service.ingest(
                role="user", text=text, session_id=session_id, order=order
            )
            native_result = native_service.ingest(
                role="user", text=text, session_id=session_id, order=order
            )

            assert _contract(python_result) == expected
            assert _contract(native_result) == expected
            assert native_result.memory_ids == python_result.memory_ids
            assert native_result.unresolved == python_result.unresolved
    finally:
        native_service.close()


def test_native_activation_can_traverse_an_edge_that_does_not_fit_prompt_budget(tmp_path: Path):
    """Traversal budget is independent from the final LLM context budget.

    The first edge is deliberately too large to render because its root concept
    is long. It must still activate ``bridge`` so the short second-hop relation
    can be selected for the prompt.
    """
    root = "root_concept_with_a_name_that_is_deliberately_long"
    session_id = "budget-bridge"
    native_service = _native_service(tmp_path, _native_library())
    python_service = _python_service(tmp_path)
    try:
        for service in (python_service, native_service):
            service.ingest(role="user", text=f"{root} is bridge", session_id=session_id, order=1)
            service.ingest(role="user", text="bridge is c", session_id=session_id, order=2)

        native = activate(
            native_service,
            concept=root,
            session_id=session_id,
            depth=2,
            budget=20,
            hop_decay=0.72,
            min_confidence=0.45,
        )
        reference = activate(
            python_service,
            concept=root,
            session_id=session_id,
            depth=2,
            budget=20,
            hop_decay=0.72,
            min_confidence=0.45,
        )

        assert reference.status == "HIT"
        assert native.status == reference.status
        assert native.selected_context == reference.selected_context == "bridge | is | c"
        assert root not in native.selected_context
        assert len(native.memory_ids) == 1
        assert len(reference.memory_ids) == 1
    finally:
        native_service.close()
