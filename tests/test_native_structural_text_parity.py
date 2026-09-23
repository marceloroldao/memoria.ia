from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from memoria_resolutiva.structural_association_field import StructuralAssociationField
from memoria_resolutiva.structural_text_recall import structural_text_symbol
from memoria_resolutiva.textual import tokenize


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "structural_text_v1_golden.json"


def _golden() -> dict:
    return json.loads(FIXTURE.read_text("utf-8"))


def _envelope(index: int, trail: list[int]) -> dict:
    return {
        "observation_id": f"golden:{index}",
        "semantic_projection": False,
        "event": {"trail": trail},
        "provenance": {"hierarchy_id": "golden"},
    }


def _python_score(field: StructuralAssociationField, query: list[int], candidate: list[int]) -> tuple[float, int, float]:
    q = tuple(dict.fromkeys(query))
    c = tuple(dict.fromkeys(candidate))
    exact = len(set(q) & set(c))
    mass = 0.0
    for qs in q:
        for cs in c:
            if qs == cs:
                continue
            mass += max(
                field.association("golden", qs, cs),
                field.association("golden", cs, qs),
            )
    normalized_mass = mass / float(len(q) * len(c))
    return exact / float(len(q)) + normalized_mass, exact, normalized_mass


def test_python_structural_text_behavior_matches_frozen_golden_vector() -> None:
    golden = _golden()
    symbols = {token: structural_text_symbol(token) for token in golden["symbols"]}
    assert symbols == golden["symbols"]
    for raw, expected in golden["casefold_vectors"].items():
        assert structural_text_symbol(raw) == expected
    for vector in golden["tokenizer_vectors"]:
        tokens = tokenize(vector["text"])
        assert tokens == vector["tokens"]
        assert [structural_text_symbol(token) for token in tokens] == vector["symbols"]

    params = golden["parameters"]
    field = StructuralAssociationField(
        max_within_distance=params["max_within_distance"],
        max_event_lag=params["max_event_lag"],
        forgetting_rate=params["forgetting_rate"],
    )
    for index, observation in enumerate(golden["observations"]):
        field.observe(_envelope(index, [symbols[token] for token in observation]))

    expected = golden["expected"]
    assert field.tick == expected["tick"]
    assert field.edge_count == expected["edge_count"]
    assert field.association(
        "golden", symbols["gato"], symbols["se"], channel="within"
    ) == pytest.approx(expected["gato_se_within"], abs=1e-12)
    assert field.association(
        "golden", symbols["gato"], symbols["dorme"], channel="within"
    ) == pytest.approx(expected["gato_dorme_within"], abs=1e-12)

    query = [symbols[token] for token in golden["query"]]
    recurrent = [symbols[token] for token in golden["candidates"]["recurrent"]]
    single = [symbols[token] for token in golden["candidates"]["single"]]
    r_score, r_exact, r_mass = _python_score(field, query, recurrent)
    s_score, s_exact, s_mass = _python_score(field, query, single)

    assert r_score == pytest.approx(expected["recurrent_score"], abs=1e-12)
    assert r_exact == expected["recurrent_exact_overlap"]
    assert r_mass == pytest.approx(expected["recurrent_association_mass"], abs=1e-12)
    assert s_score == pytest.approx(expected["single_score"], abs=1e-12)
    assert s_exact == expected["single_exact_overlap"]
    assert s_mass == pytest.approx(expected["single_association_mass"], abs=1e-12)
    assert r_score > s_score


def test_native_structural_text_kernel_matches_same_golden_vector(tmp_path: Path) -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("host C compiler is unavailable")

    mobile = ROOT / "native" / "mobile"
    binary = tmp_path / "structural_text_parity"
    command = [
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(mobile),
        str(mobile / "tests" / "structural_text_parity.c"),
        str(mobile / "structural_text_kernel.c"),
        "-lm",
        "-o",
        str(binary),
    ]
    compiled = subprocess.run(command, text=True, capture_output=True, check=False)
    assert compiled.returncode == 0, compiled.stderr

    # The native parity CLI emits UTF-8 JSON. Decode explicitly so Windows\n    # does not reinterpret non-ASCII token keys through the active code page.\n    executed = subprocess.run(\n        [str(binary)],\n        text=True,\n        encoding="utf-8",\n        capture_output=True,\n        check=False,\n    )
    assert executed.returncode == 0, executed.stderr
    native = json.loads(executed.stdout)
    golden = _golden()
    expected = golden["expected"]

    assert native["symbols"] == golden["symbols"]
    assert native["casefold"] == golden["casefold_vectors"]
    assert native["tokenizer"] == [
        vector["symbols"] for vector in golden["tokenizer_vectors"]
    ]
    assert native["tick"] == expected["tick"]
    assert native["edge_count"] == expected["edge_count"]
    assert native["gato_se_within"] == pytest.approx(expected["gato_se_within"], abs=1e-12)
    assert native["gato_dorme_within"] == pytest.approx(expected["gato_dorme_within"], abs=1e-12)
    assert native["recurrent"]["score"] == pytest.approx(expected["recurrent_score"], abs=1e-12)
    assert native["recurrent"]["exact_overlap"] == expected["recurrent_exact_overlap"]
    assert native["recurrent"]["association_mass"] == pytest.approx(
        expected["recurrent_association_mass"], abs=1e-12
    )
    assert native["single"]["score"] == pytest.approx(expected["single_score"], abs=1e-12)
    assert native["single"]["exact_overlap"] == expected["single_exact_overlap"]
    assert native["single"]["association_mass"] == pytest.approx(
        expected["single_association_mass"], abs=1e-12
    )
    assert native["recurrent"]["score"] > native["single"]["score"]
