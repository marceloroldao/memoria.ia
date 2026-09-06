from pathlib import Path
import os
import shutil
import subprocess

import pytest


def test_rc5_conversational_corpus(tmp_path: Path) -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("C compiler is required for RC5 conversational corpus")

    repo = Path(__file__).resolve().parents[1]
    mobile = repo / "native" / "mobile"
    binary_name = "rc5_conversational_corpus.exe" if os.name == "nt" else "rc5_conversational_corpus"
    binary = tmp_path / binary_name

    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{mobile}",
            str(mobile / "tests" / "rc5_conversational_corpus.c"),
            str(mobile / "concept_relation_adapter.c"),
            str(mobile / "concept_relation_traversal.c"),
            str(mobile / "concept_relation_collection.c"),
            str(mobile / "concept_identity_kernel.c"),
            "-o",
            str(binary),
        ],
        cwd=repo,
        check=True,
    )
    assert binary.is_file()
    subprocess.run([str(binary)], cwd=repo, check=True)
