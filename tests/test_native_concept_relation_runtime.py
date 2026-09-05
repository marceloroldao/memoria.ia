from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_concept_relation_runtime_composes_adapter_and_traversal(tmp_path: Path) -> None:
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("C compiler not available")
    root = Path(__file__).resolve().parents[1]
    mobile = root / "native" / "mobile"
    binary = tmp_path / "concept_relation_runtime_test"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{mobile}",
            str(mobile / "tests" / "concept_relation_runtime.c"),
            str(mobile / "concept_relation_runtime.c"),
            str(mobile / "concept_relation_adapter.c"),
            str(mobile / "concept_identity_kernel.c"),
            str(mobile / "concept_relation_traversal.c"),
            "-o",
            str(binary),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run([str(binary)], check=True, text=True, capture_output=True)
