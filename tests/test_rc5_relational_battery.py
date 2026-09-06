from pathlib import Path
import shutil
import subprocess


def test_rc5_relational_battery(tmp_path: Path) -> None:
    cc = shutil.which("cc")
    if cc is None:
        raise RuntimeError("C compiler is required for RC5 relational battery")

    repo = Path(__file__).resolve().parents[1]
    mobile = repo / "native" / "mobile"
    binary = tmp_path / "rc5_relational_battery"

    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{mobile}",
            str(mobile / "tests" / "rc5_relational_battery.c"),
            str(mobile / "concept_relation_traversal.c"),
            "-o",
            str(binary),
        ],
        cwd=repo,
        check=True,
    )
    subprocess.run([str(binary)], cwd=repo, check=True)
