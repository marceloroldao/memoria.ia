from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


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
