from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_native_concept_relation_neighborhood(tmp_path: Path) -> None:
    cc = shutil.which("cc")
    if cc is None:
        raise RuntimeError("C compiler is required for native concept relation neighborhood test")

    repo = Path(__file__).resolve().parents[1]
    mobile = repo / "native" / "mobile"
    binary = tmp_path / "concept_relation_neighborhood"
    cmd = [
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        f"-I{mobile}",
        str(mobile / "tests" / "concept_relation_neighborhood.c"),
        str(mobile / "concept_relation_neighborhood.c"),
        str(mobile / "concept_relation_adapter.c"),
        str(mobile / "concept_identity_kernel.c"),
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, cwd=repo, check=True)
    subprocess.run([str(binary)], cwd=repo, check=True)
