from pathlib import Path
import shutil
import subprocess


def test_native_concept_relation_collection(tmp_path: Path) -> None:
    cc = shutil.which("cc")
    if cc is None:
        raise RuntimeError("C compiler is required for native concept relation collection test")

    repo = Path(__file__).resolve().parents[1]
    mobile = repo / "native" / "mobile"
    binary = tmp_path / "concept_relation_collection"
    cmd = [
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        f"-I{mobile}",
        str(mobile / "tests" / "concept_relation_collection.c"),
        str(mobile / "concept_relation_collection.c"),
        str(mobile / "concept_relation_adapter.c"),
        str(mobile / "concept_identity_kernel.c"),
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, cwd=repo, check=True)
    subprocess.run([str(binary)], cwd=repo, check=True)
