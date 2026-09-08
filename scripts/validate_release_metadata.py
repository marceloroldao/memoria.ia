from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELEASE_VERSION = "1.0.0-rc7"
EXPECTED_PACKAGE_VERSION = "1.0.0rc7"
EXPECTED_RELEASE_DATE = "2026-09-08"
EXPECTED_TITLE = "memoria.ia: Resolutive Memory — v1.0.0 Release Candidate 7"
EXPECTED_CFF_TITLE = "memoria.ia: Resolutive Memory — v1.0 Release Candidate 7"
EXPECTED_ORCID = "0009-0003-6075-4680"
PREVIOUS_ARCHIVAL_DOI = "10.5281/zenodo.22648409"
PREVIOUS_PUBLIC_TAG = "v1.0.0-rc6"
FREEZE_COMMIT = "ca4089cad0369da3a13c484c93cc4c97ee54cfaf"
LAST_RUNTIME_COMMIT = "3f72f7e46c976245818e8878e36f6d906d6ba0ba"


def fail(message: str) -> None:
    raise SystemExit(f"metadata gate: FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    package_version = pyproject["project"]["version"]
    require(package_version == EXPECTED_PACKAGE_VERSION, f"pyproject version is {package_version!r}")

    zenodo = json.loads((ROOT / ".zenodo.json").read_text("utf-8"))
    require(zenodo.get("upload_type") == "software", "Zenodo upload_type must be software")
    require(zenodo.get("version") == EXPECTED_RELEASE_VERSION, "Zenodo version mismatch")
    require(zenodo.get("title") == EXPECTED_TITLE, "Zenodo title mismatch")
    require(zenodo.get("access_right") == "open", "Zenodo access_right must be open")
    require(zenodo.get("language") == "eng", "Zenodo language must be eng")
    require("doi" not in zenodo, "RC7 preparation must not pre-assign a DOI")
    require("license" not in zenodo, "custom RRNCL must not be sent as a Zenodo license identifier")
    creators = zenodo.get("creators")
    require(isinstance(creators, list) and len(creators) == 1, "Zenodo must contain exactly one creator")
    creator = creators[0]
    require(creator.get("name") == "Matos, Marcelo Roldão", "Zenodo creator name mismatch")
    require(creator.get("orcid") == EXPECTED_ORCID, "Zenodo ORCID mismatch")
    require(bool(re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", creator["orcid"])), "Zenodo ORCID shape is invalid")

    related = zenodo.get("related_identifiers", [])
    require(any(i.get("identifier") == f"https://doi.org/{PREVIOUS_ARCHIVAL_DOI}" and i.get("relation") == "isNewVersionOf" for i in related if isinstance(i, dict)), "Zenodo archival lineage mismatch")
    require(any(i.get("identifier", "").endswith(f"/releases/tag/{PREVIOUS_PUBLIC_TAG}") and i.get("relation") == "isNewVersionOf" for i in related if isinstance(i, dict)), "Zenodo previous public tag mismatch")

    cff = (ROOT / "CITATION.cff").read_text("utf-8")
    require(f'title: "{EXPECTED_CFF_TITLE}"' in cff, "CITATION.cff title mismatch")
    require('version: "1.0.0-rc.7"' in cff, "CITATION.cff version mismatch")
    require(f'date-released: "{EXPECTED_RELEASE_DATE}"' in cff, "CITATION.cff date mismatch")
    require(f'https://orcid.org/{EXPECTED_ORCID}' in cff, "CITATION.cff ORCID mismatch")
    require("doi:" not in cff, "RC7 preparation must not pre-assign a DOI")

    readme = (ROOT / "README.md").read_text("utf-8")
    require("v1.0.0-rc7" in readme and "1.0.0rc7" in readme, "README does not identify RC7")
    require(FREEZE_COMMIT in readme, "README missing RC7 cumulative freeze commit")
    require(LAST_RUNTIME_COMMIT in readme, "README missing RC7 last runtime-changing commit")
    require(PREVIOUS_ARCHIVAL_DOI in readme, "README missing previous RC6 archival DOI")
    require("RSMS 1.0-rc.1" in readme, "README missing RSMS compatibility boundary")

    notes = (ROOT / "RELEASE_NOTES_v1.0.0-rc7.md").read_text("utf-8")
    require(FREEZE_COMMIT in notes, "RC7 release notes missing cumulative freeze commit")
    require(LAST_RUNTIME_COMMIT in notes, "RC7 release notes missing last runtime-changing commit")
    require(PREVIOUS_ARCHIVAL_DOI in notes, "RC7 release notes missing archival lineage")
    require("RC7 is a stabilization-only release candidate" in notes, "RC7 stabilization scope statement missing")
    require("A new RC7 DOI must be inserted only after the archival record exists" in notes, "RC7 DOI publication boundary missing")

    json.dumps(zenodo, ensure_ascii=False)
    print("metadata gate: PASS")
    print(f"release_version={EXPECTED_RELEASE_VERSION}")
    print(f"package_version={EXPECTED_PACKAGE_VERSION}")
    print(f"freeze_commit={FREEZE_COMMIT}")
    print(f"last_runtime_commit={LAST_RUNTIME_COMMIT}")
    print("rc7_doi_preassigned=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
