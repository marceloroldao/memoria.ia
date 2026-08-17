from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def require(path: str) -> None:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"missing required release artifact: {path}")


def main() -> int:
    for path in (
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "pyproject.toml",
        "docs/COMPATIBILITY.md",
        "docs/REPRODUCIBILITY.md",
    ):
        require(path)

    from memoria_resolutiva import ResolutiveMemoryAPI, __version__

    if __version__ != "0.95.0":
        raise SystemExit(f"unexpected package version: {__version__}")
    if ResolutiveMemoryAPI.API_VERSION != "0.95.0":
        raise SystemExit(f"unexpected API version: {ResolutiveMemoryAPI.API_VERSION}")

    cmd = [sys.executable, "-m", "pytest", "-q"]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode:
        return result.returncode

    print("v0.95 release gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
