from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_concept_identity_kernel_compiles_and_runs(tmp_path: Path):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("host C compiler is unavailable")
    root = Path(__file__).resolve().parents[1]
    mobile = root / "native" / "mobile"
    binary = tmp_path / "concept_identity_kernel_test"
    command = [
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(mobile),
        str(mobile / "tests" / "concept_identity_kernel.c"),
        str(mobile / "concept_identity_kernel.c"),
        "-o",
        str(binary),
    ]
    compiled = subprocess.run(command, text=True, capture_output=True, check=False)
    assert compiled.returncode == 0, compiled.stderr
    executed = subprocess.run([str(binary)], text=True, capture_output=True, check=False)
    assert executed.returncode == 0, executed.stderr
