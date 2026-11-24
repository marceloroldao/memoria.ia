from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_concept_catalog import NativeConceptCatalog
from memoria_resolutiva.native_conversation import NativeConversationService


class _Lease:
    def __init__(self, *, changed: bool):
        self.changed = changed
        self.calls = []
        self.released = False

    def supports(self, name: str) -> bool:
        return name == "memoria_mobile_apply_concept_catalog_json"

    def call(self, name: str, payload: dict[str, object]):
        self.calls.append((name, payload))
        return 0, {
            "status": "OK",
            "changed": self.changed,
            "concept_count": payload["concept_count"],
            "fingerprint": payload["fingerprint"],
        }

    def release(self):
        self.released = True


class _Manager:
    def __init__(self, lease: _Lease):
        self.lease = lease

    def acquire(self, **_kwargs):
        return self.lease


def _catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(
        schema=1,
        namespace="semantic",
        concepts=(),
        fingerprint="sha256:" + "b" * 64,
    )


def test_native_conversation_materializes_catalog_through_owned_lease(tmp_path):
    lease = _Lease(changed=True)
    service = NativeConversationService(
        library_path=tmp_path / "unused.so",
        data_dir=tmp_path / "native",
        organization_id="org-a",
        runtime_manager=_Manager(lease),
    )
    assert service.materialize_concept_catalog(_catalog()) is True
    assert lease.calls[0][0] == "memoria_mobile_apply_concept_catalog_json"
    assert lease.calls[0][1]["concept_count"] == 0
    service.close()
    assert lease.released is True


def test_native_conversation_materialization_preserves_idempotent_noop(tmp_path):
    lease = _Lease(changed=False)
    service = NativeConversationService(
        library_path=tmp_path / "unused.so",
        data_dir=tmp_path / "native",
        organization_id="org-a",
        runtime_manager=_Manager(lease),
    )
    assert service.materialize_concept_catalog(_catalog()) is False


def test_confirmed_entity_aliases_resolve_attributes_after_reopen(tmp_path):
    library_path = os.environ.get("MEMORIA_NATIVE_LIB")
    if not library_path:
        pytest.skip("MEMORIA_NATIVE_LIB is required for the native catalog integration test")

    def open_service(concept_namespace="equipment"):
        return closing(NativeConversationService(
            library_path=Path(library_path),
            data_dir=tmp_path / "native",
            organization_id="org-equipment",
            concept_namespace=concept_namespace,
        ))

    def catalog(fingerprint_char, *concepts):
        return NativeConceptCatalog(
            schema=1,
            namespace="equipment",
            concepts=concepts,
            fingerprint="sha256:" + fingerprint_char * 64,
        )

    scale = {
        "concept_id": "scale-lotus",
        "namespace": "equipment",
        "canonical": "balança Lótus",
        "aliases": ["medidor da feira", "aferidor da bancada", "equipamento"],
    }
    bag = {
        "concept_id": "bag-north",
        "namespace": "equipment",
        "canonical": "maleta Norte",
        "aliases": ["equipamento"],
    }
    query = "Qual é a cor do medidor da feira?"

    with open_service() as service:
        previous = service.ingest(
            role="user", text="A balança Lótus é verde.", session_id="workshop", order=10,
        )
        service.ingest(
            role="user", text="O medidor da feira é a balança Lótus.", session_id="workshop", order=11,
        )
        assert service.resolve(query=query, session_id="workshop").status == "UNRESOLVED"
        assert service.materialize_concept_catalog(catalog("a", scale, bag))
        before = service.resolve(query=query, session_id="workshop")
        assert before.selected_context == "A balança Lótus é verde."
        assert before.provenance[0]["ultimate_source_memory_id"] == previous.memory_ids[0]

        updated = service.ingest(
            role="user", text="O aferidor da bancada é amarelo.", session_id="workshop", order=20,
        )
        historical = service.ingest(
            role="user", text="A balança Lótus é cinza.", session_id="workshop", order=15,
        )
        service.ingest(
            role="user", text="O medidor da feira é azul.", session_id="other", order=30,
        )
        service.ingest(
            role="assistant", text="O medidor da feira é branco.", session_id="workshop", order=40,
        )
        service.ingest(
            role="user", text="O equipamento é vermelho.", session_id="workshop", order=50,
        )
        service.flush()

    with open_service() as service:
        for mention in ("balança Lótus", "medidor da feira", "aferidor da bancada"):
            result = service.resolve(query=f"Qual a cor de {mention}?", session_id="workshop")
            assert result.selected_context == "O aferidor da bancada é amarelo."
            assert result.provenance[0]["ultimate_source_memory_id"] == updated.memory_ids[0]
            assert result.relations[0]["predicate"] == "color"

        for mention in ("balança Lótus", "medidor da feira", "aferidor da bancada"):
            past = service.resolve(
                query=f"De que cor era a {mention} antes?", session_id="workshop",
            )
            present = service.resolve(
                query=f"Qual a cor da {mention} agora?", session_id="workshop",
            )
            assert past.memory_ids == present.memory_ids == (historical.memory_ids[0], updated.memory_ids[0])
            assert past.relations[0]["object"] == "cinza"
            assert past.relations[0]["subject"] == "balança Lótus"
            assert past.provenance[0]["memory_id"] == historical.memory_ids[0]
            assert present.relations[0]["object"] == "amarelo"
            assert present.relations[0]["subject"] == "aferidor da bancada"
            assert present.provenance[1]["memory_id"] == updated.memory_ids[0]

        change = service.resolve(query="O que mudou no medidor da feira?", session_id="workshop")
        assert change.memory_ids == (historical.memory_ids[0], updated.memory_ids[0])
        assert change.selected_context == (
            "PREVIOUS: A balança Lótus é cinza.\nCURRENT: O aferidor da bancada é amarelo."
        )
        assert change.relations[0]["predicate"] == "color"

        for question in (
            "Qual a cor do equipamento?",
            "Quanto pesa o medidor da feira?",
            "Onde ficava a balança Lótus antes?",
            "Qual era a cor do equipamento antes?",
            "O que mudou no equipamento?",
            "Qual a cor da balança Lótus e da maleta Norte agora?",
        ):
            assert service.resolve(query=question, session_id="workshop").status == "UNRESOLVED"

        assert service.resolve(query=query, session_id="other").selected_context == "O medidor da feira é azul."

        service.ingest(role="user", text="A balança Lótus pesa 3 quilos.", session_id="workshop", order=15)
        service.ingest(role="user", text="A balança Lótus pesa 5 quilos.", session_id="workshop", order=20)
        changes = service.resolve(query="O que mudou no medidor da feira?", session_id="workshop")
        assert changes.status == "HIT"
        assert [
            (change["property"], change["previous_value"], change["current_value"])
            for change in changes.temporal_changes
        ] == [("color", "cinza", "amarelo"), ("weight", "3 quilos", "5 quilos")]

    with open_service("another_catalog") as service:
        assert service.resolve(query=query, session_id="workshop").status == "UNRESOLVED"
        assert service.resolve(
            query="Qual era a cor do medidor da feira antes?", session_id="workshop",
        ).status == "UNRESOLVED"

    with open_service() as service:
        assert service.materialize_concept_catalog(catalog("b", {
            **scale, "aliases": ["aferidor da bancada"],
        }, bag))
        assert service.resolve(query=query, session_id="workshop").status == "UNRESOLVED"

    with open_service() as service:
        assert service.resolve(query=query, session_id="workshop").status == "UNRESOLVED"
        assert service.resolve(
            query="Qual a cor da balança Lótus?", session_id="workshop",
        ).selected_context == "O aferidor da bancada é amarelo."
        assert service.resolve(
            query="Qual era a cor do medidor da feira antes?", session_id="workshop",
        ).status == "UNRESOLVED"


@pytest.mark.parametrize(("canonical", "alias", "old_text", "new_text", "old_query", "new_query",
                          "property_name", "old_value", "new_value"), [
    (
        "maleta Norte", "caixa de ferramentas",
        "A maleta Norte pesa 9,5 quilos.", "A caixa de ferramentas pesa 12 quilos.",
        "Quanto pesava a caixa de ferramentas antes?", "Qual o peso atual da caixa de ferramentas?",
        "weight", "9,5 quilos", "12 quilos",
    ),
    (
        "bicicleta Índigo", "bike de passeio",
        "A dona da bicicleta Índigo é Lia.", "A bike de passeio pertence a Iara.",
        "A quem pertencia a bike de passeio antes?", "Quem é a proprietária da bike de passeio agora?",
        "owner", "Lia", "Iara",
    ),
    (
        "ônibus Aurora", "circular da praça",
        "O motorista do ônibus Aurora é Rui.", "O motorista do circular da praça é Caio.",
        "Quem dirigia o circular da praça antes?", "Quem é o motorista do circular da praça agora?",
        "driver", "Rui", "Caio",
    ),
])
def test_confirmed_aliases_resolve_more_temporal_attributes(
    tmp_path, canonical, alias, old_text, new_text, old_query, new_query,
    property_name, old_value, new_value,
):
    library_path = os.environ.get("MEMORIA_NATIVE_LIB")
    if not library_path:
        pytest.skip("MEMORIA_NATIVE_LIB is required for the native catalog integration test")

    def open_service():
        return closing(NativeConversationService(
            library_path=Path(library_path),
            data_dir=tmp_path / "native",
            organization_id="org-temporal-attributes",
            concept_namespace="objects",
        ))

    with open_service() as service:
        service.materialize_concept_catalog(NativeConceptCatalog(
            schema=1,
            namespace="objects",
            concepts=({
                "concept_id": "object-a",
                "namespace": "objects",
                "canonical": canonical,
                "aliases": [alias],
            },),
            fingerprint="sha256:" + "c" * 64,
        ))
        new = service.ingest(role="user", text=new_text, session_id="habits", order=20)
        old = service.ingest(role="user", text=old_text, session_id="habits", order=10)
        service.ingest(role="user", text=new_text, session_id="other", order=1)
        service.ingest(role="assistant", text=old_text, session_id="habits", order=40)
        service.flush()

    with open_service() as service:
        for query, value in ((old_query, old_value), (new_query, new_value)):
            result = service.resolve(query=query, session_id="habits")
            assert result.memory_ids == (old.memory_ids[0], new.memory_ids[0])
            assert result.relations[0]["predicate"] == property_name
            assert result.relations[0]["object"] == value
        assert service.resolve(query=old_query, session_id="other").status == "UNRESOLVED"
        missing_entity = new_query.replace(alias, "computador ausente")
        assert service.resolve(query=missing_entity, session_id="habits").status == "UNRESOLVED"
