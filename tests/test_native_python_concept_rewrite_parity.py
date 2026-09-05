from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from memoria_resolutiva.concept_aware_conversation import rewrite_query_with_explicit_concepts
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


ROOT = Path(__file__).resolve().parents[1]


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


@pytest.fixture(scope="session")
def native_concept_rewrite_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        pytest.skip("a C compiler is required for direct native concept rewrite parity")
    output = tmp_path_factory.mktemp("native-concept-rewrite") / "concept_query_rewrite_cli"
    mobile = ROOT / "native" / "mobile"
    subprocess.run(
        [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(mobile),
            str(mobile / "tests" / "concept_query_rewrite_cli.c"),
            str(mobile / "concept_query_rewrite.c"),
            str(mobile / "concept_identity_kernel.c"),
            "-o",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    assert output.is_file()
    return output


def _native(cli: Path, query: str) -> tuple[str, str | None, str, tuple[str, ...]]:
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
def test_native_concept_rewrite_matches_python_reference(
    native_concept_rewrite_cli: Path,
    query: str,
):
    store = _store()
    reference = rewrite_query_with_explicit_concepts(
        store,
        _scope(),
        query,
        namespace="semantic",
        max_alias_words=6,
    )
    native_status, native_reason, native_query, native_ids = _native(native_concept_rewrite_cli, query)

    assert native_status == reference.status
    assert native_reason == reference.reason
    assert native_query == reference.rewritten_query
    assert native_ids == reference.concept_ids
