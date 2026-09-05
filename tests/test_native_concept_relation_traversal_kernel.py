from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_concept_relation_traversal_kernel(tmp_path: Path) -> None:
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("C compiler is unavailable")
    root = Path(__file__).resolve().parents[1]
    binary = tmp_path / "concept_relation_traversal"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(root / "native" / "mobile"),
            str(root / "native" / "mobile" / "tests" / "concept_relation_traversal.c"),
            str(root / "native" / "mobile" / "concept_relation_traversal.c"),
            "-o",
            str(binary),
        ],
        check=True,
        cwd=root,
    )
    subprocess.run([str(binary)], check=True, cwd=root)
