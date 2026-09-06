from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_rc5_relation_scale_probe(tmp_path: Path) -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        pytest.skip("a C compiler is required for RC5 scale probe")

    exe = tmp_path / ("rc5_relation_scale.exe" if os.name == "nt" else "rc5_relation_scale")
    mobile = ROOT / "native" / "mobile"
    subprocess.run(
        [
            compiler,
            "-std=c11",
            "-O2",
            "-I",
            str(mobile),
            str(mobile / "tests" / "rc5_relation_scale.c"),
            str(mobile / "concept_relation_traversal.c"),
            "-o",
            str(exe),
        ],
        check=True,
        cwd=ROOT,
    )
    completed = subprocess.run([str(exe)], check=True, text=True, capture_output=True, cwd=ROOT)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("edges=")]
    assert len(lines) == 4

    observed = {}
    for line in lines:
        fields = dict(item.split("=", 1) for item in line.split())
        observed[int(fields["edges"])] = {
            "latency_ms": float(fields["latency_ms"]),
            "paths": int(fields["paths"]),
            "hops": int(fields["hops"]),
        }

    assert set(observed) == {100, 1000, 10000, 50000}
    assert all(row["paths"] >= 1 for row in observed.values())
    assert all(row["hops"] == 4 for row in observed.values())

    # CI timings are observational, not a hard performance contract. Keep only a very generous
    # runaway guard so pathological regressions fail without treating shared-runner timing as absolute.
    assert observed[50000]["latency_ms"] < 30000.0

    print("RC5 relation scale probe")
    for edges in sorted(observed):
        row = observed[edges]
        print(f"edges={edges} latency_ms={row['latency_ms']:.3f} paths={row['paths']} hops={row['hops']}")
