from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from memoria_resolutiva.concept_aware_conversation import rewrite_query_with_explicit_concepts
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _scope() -> MemoryScope:
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _store() -> PersistentSemanticConceptStore:
    store = PersistentSemanticConceptStore(
        EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    )
    store.register_concept(
        _scope(),
        "voltage",
        aliases=("ddp", "diferença de potencial", "potential difference"),
        namespace="semantic",
        sense_key="electric potential",
        concept_id="concept:voltage",
    )
    store.register_concept(
        _scope(),
        "financial bank",
        aliases=("bank",),
        namespace="semantic",
        sense_key="finance",
        concept_id="concept:bank-finance",
        context_cues=("loan", "credit"),
    )
    store.register_concept(
        _scope(),
        "river bank",
        aliases=("bank",),
        namespace="semantic",
        sense_key="geography",
        concept_id="concept:bank-river",
        context_cues=("river", "water"),
    )
    return store


def _native(query: str) -> tuple[str, str | None, str, tuple[str, ...]]:
    raw = os.environ.get("MEMORIA_NATIVE_CONCEPT_REWRITE_CLI")
    if not raw:
        pytest.skip("MEMORIA_NATIVE_CONCEPT_REWRITE_CLI is required for native concept rewrite parity")
    cli = Path(raw)
    assert cli.is_file(), f"native concept rewrite CLI not found: {cli}"
    completed = subprocess.run([str(cli), query], check=True, text=True, capture_output=True)
    status, reason, rewritten, ids_csv = completed.stdout.rstrip("\n").split("\t")
    ids = tuple(value for value in ids_csv.split(",") if value)
    return status, reason or None, rewritten, ids


@pytest.mark.parametrize(
    "query",
    [
        "qual a DDP do charger",
        "qual a diferença de potencial do charger",
        "measure the potential difference now",
        "voltage status",
        "bank status",
        "loan status for bank",
        "water status for bank",
        "loan and river context for bank status",
        "temperatura externa",
    ],
)
def test_native_concept_rewrite_matches_python_reference(query: str):
    store = _store()
    reference = rewrite_query_with_explicit_concepts(
        store,
        _scope(),
        query,
        namespace="semantic",
        max_alias_words=6,
    )
    native_status, native_reason, native_query, native_ids = _native(query)

    assert native_status == reference.status
    assert native_reason == reference.reason
    assert native_query == reference.rewritten_query
    assert native_ids == reference.concept_ids
