from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "native" / "mobile"
CASE = MOBILE / "tests" / "rc6_relational_projection_regression.c"


def test_rc6_relational_projection_native(tmp_path: Path) -> None:
    """Freeze projection reuse and generative contamination barriers for RC6."""
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("native C compiler is not available")

    binary = tmp_path / "rc6_relational_projection_regression"
    command = [
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(MOBILE),
        str(CASE),
        str(MOBILE / "concept_relation_collection.c"),
        str(MOBILE / "concept_relation_neighborhood.c"),
        str(MOBILE / "concept_relation_adapter.c"),
        str(MOBILE / "concept_identity_kernel.c"),
        "-o",
        str(binary),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, capture_output=True, text=True)
