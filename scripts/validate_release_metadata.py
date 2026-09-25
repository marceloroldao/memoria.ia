from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_VERSION = "2.0.0-rc2"
PACKAGE_VERSION = "2.0.0rc2"
CANDIDATE_TAG = "v2.0.0-rc2"
CANDIDATE_TITLE = "memoria.ia: Resolutive Memory — v2.0.0 Release Candidate 2"
CFF_TITLE = "memoria.ia: Resolutive Memory — v2.0 Release Candidate 2"
RC1_DOI = "10.5281/zenodo.22908785"
RC1_FREEZE = "bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9"
RC1_BDR = "d09914b85646353d8fd004ccf99e96a94fab9eef"
RC2_FREEZE = "e240bf2197000f955d65edec5dba47045d9f237e"
RC2_BDR = "317882a00f041fc1568ff986af8016b09453f21a"
ORCID = "0009-0003-6075-4680"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"metadata gate: FAIL: {message}")


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    require(pyproject["project"]["version"] == PACKAGE_VERSION, "RC2 package version mismatch")

    zenodo = json.loads((ROOT / ".zenodo.json").read_text("utf-8"))
    require(zenodo.get("upload_type") == "software", "Zenodo upload_type mismatch")
    require(zenodo.get("version") == CANDIDATE_VERSION, "Zenodo RC2 version mismatch")
    require(zenodo.get("title") == CANDIDATE_TITLE, "Zenodo RC2 title mismatch")
    require(zenodo.get("access_right") == "open", "Zenodo access_right mismatch")
    require(zenodo.get("language") == "eng", "Zenodo language mismatch")
    require("doi" not in zenodo, "unassigned RC2 DOI must not be claimed")
    require("license" not in zenodo, "custom RRNCL must not be sent as a Zenodo license identifier")
    creators = zenodo.get("creators")
    require(isinstance(creators, list) and len(creators) == 1, "Zenodo creator count mismatch")
    require(creators[0].get("name") == "Matos, Marcelo Roldão", "Zenodo creator mismatch")
    require(creators[0].get("orcid") == ORCID, "Zenodo ORCID mismatch")
    require(bool(re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", ORCID)), "ORCID shape invalid")
    related = zenodo.get("related_identifiers", [])
    require(any(i.get("identifier") == f"https://doi.org/{RC1_DOI}" and i.get("relation") == "isNewVersionOf" for i in related if isinstance(i, dict)), "RC1 DOI lineage missing")
    require(any(i.get("identifier", "").endswith(f"/releases/tag/{CANDIDATE_TAG}") and i.get("relation") == "isSupplementTo" for i in related if isinstance(i, dict)), "RC2 GitHub tag relation missing")
    require(not any(i.get("relation") == "isIdenticalTo" for i in related if isinstance(i, dict)), "unassigned RC2 identity relation present")

    cff = (ROOT / "CITATION.cff").read_text("utf-8")
    require(f'title: "{CFF_TITLE}"' in cff, "CITATION RC2 title mismatch")
    require('version: "2.0.0-rc.2"' in cff, "CITATION RC2 version mismatch")
    require('date-released: "2026-09-25"' in cff, "CITATION date mismatch")
    require(f"https://orcid.org/{ORCID}" in cff, "CITATION ORCID mismatch")
    require("doi:" not in cff, "CITATION must not claim unassigned RC2 DOI")

    readme = (ROOT / "README.md").read_text("utf-8")
    require(CANDIDATE_TAG in readme and PACKAGE_VERSION in readme, "README RC2 identity missing")
    require(RC2_FREEZE in readme and RC2_BDR in readme, "README RC2 freeze/BDR missing")
    require(RC1_FREEZE in readme and RC1_DOI in readme and RC1_BDR in readme, "README RC1 history missing")
    require(RC2_BDR in (ROOT / "Dockerfile").read_text("utf-8"), "Dockerfile BDR pin mismatch")
    for workflow in ("android-mobile-abi.yml", "native-shared-bdr-reopen.yml"):
        require(RC2_BDR in (ROOT / ".github" / "workflows" / workflow).read_text("utf-8"), f"{workflow} BDR pin mismatch")

    old_notes = (ROOT / "RELEASE_NOTES_v2.0.0-rc1.md").read_text("utf-8")
    require(RC1_FREEZE in old_notes and RC1_BDR in old_notes and RC1_DOI in old_notes, "RC1 archived notes changed")
    notes = (ROOT / "RELEASE_NOTES_v2.0.0-rc2.md").read_text("utf-8")
    record = (ROOT / "docs/V2_RC2_FREEZE_RECORD.md").read_text("utf-8")
    require("GitHub publication candidate" in notes, "RC2 publication status missing")
    require(RC2_FREEZE in notes and RC2_FREEZE in record, "RC2 functional freeze missing")
    require(RC2_BDR in notes and RC2_BDR in record, "RC2 BDR provenance missing")
    require("36077501782" in record and "36077501751" in record, "cross-repository CI evidence missing")

    print("metadata gate: PASS")
    print(f"candidate={CANDIDATE_TAG}")
    print(f"package={PACKAGE_VERSION}")
    print(f"functional_freeze={RC2_FREEZE}")
    print(f"bdr_pin={RC2_BDR}")
    print(f"previous_doi={RC1_DOI}")
    print("rc2_doi=unassigned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
