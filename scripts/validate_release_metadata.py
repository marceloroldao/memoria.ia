from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELEASE_VERSION = "2.0.0-rc1"
EXPECTED_PACKAGE_VERSION = "2.0.0rc1"
EXPECTED_RELEASE_DATE = "2026-09-23"
EXPECTED_TITLE = "memoria.ia: Resolutive Memory — v2.0.0 Release Candidate 1"
EXPECTED_CFF_TITLE = "memoria.ia: Resolutive Memory — v2.0 Release Candidate 1"
EXPECTED_ORCID = "0009-0003-6075-4680"
CURRENT_ARCHIVAL_DOI = "10.5281/zenodo.22908785"
PREVIOUS_ARCHIVAL_DOI = "10.5281/zenodo.22654141"
CURRENT_PUBLIC_TAG = "v2.0.0-rc1"
FREEZE_COMMIT = "bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9"
VALIDATED_BDR_COMMIT = "d09914b85646353d8fd004ccf99e96a94fab9eef"


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
    require(zenodo.get("doi") == CURRENT_ARCHIVAL_DOI, "Zenodo current DOI mismatch")
    require("license" not in zenodo, "custom RRNCL must not be sent as a Zenodo license identifier")

    creators = zenodo.get("creators")
    require(isinstance(creators, list) and len(creators) == 1, "Zenodo must contain exactly one creator")
    creator = creators[0]
    require(creator.get("name") == "Matos, Marcelo Roldão", "Zenodo creator name mismatch")
    require(creator.get("orcid") == EXPECTED_ORCID, "Zenodo ORCID mismatch")
    require(bool(re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", creator["orcid"])), "Zenodo ORCID shape is invalid")

    related = zenodo.get("related_identifiers", [])
    require(any(i.get("identifier") == f"https://doi.org/{CURRENT_ARCHIVAL_DOI}" and i.get("relation") == "isIdenticalTo" for i in related if isinstance(i, dict)), "Zenodo current DOI relation mismatch")
    require(any(i.get("identifier") == f"https://doi.org/{PREVIOUS_ARCHIVAL_DOI}" and i.get("relation") == "isNewVersionOf" for i in related if isinstance(i, dict)), "Zenodo archival lineage mismatch")
    require(any(i.get("identifier", "").endswith(f"/releases/tag/{CURRENT_PUBLIC_TAG}") and i.get("relation") == "isSupplementTo" for i in related if isinstance(i, dict)), "Zenodo current public tag mismatch")

    cff = (ROOT / "CITATION.cff").read_text("utf-8")
    require(f'title: "{EXPECTED_CFF_TITLE}"' in cff, "CITATION.cff title mismatch")
    require('version: "2.0.0-rc.1"' in cff, "CITATION.cff version mismatch")
    require(f'date-released: "{EXPECTED_RELEASE_DATE}"' in cff, "CITATION.cff date mismatch")
    require(f'https://orcid.org/{EXPECTED_ORCID}' in cff, "CITATION.cff ORCID mismatch")
    require(f'doi: "{CURRENT_ARCHIVAL_DOI}"' in cff, "V2 RC1 CITATION DOI mismatch")

    readme = (ROOT / "README.md").read_text("utf-8")
    require("v2.0.0-rc1" in readme and "2.0.0rc1" in readme, "README does not identify V2 RC1")
    require(FREEZE_COMMIT in readme, "README missing V2 RC1 functional freeze commit")
    require(VALIDATED_BDR_COMMIT in readme, "README missing validated BDR pin")
    require(CURRENT_ARCHIVAL_DOI in readme, "README missing V2 RC1 archival DOI")
    require(PREVIOUS_ARCHIVAL_DOI in readme, "README missing previous RC7 archival DOI")

    notes = (ROOT / "RELEASE_NOTES_v2.0.0-rc1.md").read_text("utf-8")
    require(FREEZE_COMMIT in notes, "V2 RC1 release notes missing functional freeze commit")
    require(VALIDATED_BDR_COMMIT in notes, "V2 RC1 release notes missing validated BDR pin")
    require(PREVIOUS_ARCHIVAL_DOI in notes, "V2 RC1 release notes missing archival lineage")
    require(CURRENT_ARCHIVAL_DOI in notes, "V2 RC1 release notes missing current archival DOI")
    require("The V2 RC1 DOI was registered after the GitHub pre-release was published" in notes, "V2 RC1 DOI registration statement missing")
    require("does not include the planned Resolutive Inference Engine" in notes, "V2 RC1 scope boundary missing")

    json.dumps(zenodo, ensure_ascii=False)
    print("metadata gate: PASS")
    print(f"release_version={EXPECTED_RELEASE_VERSION}")
    print(f"package_version={EXPECTED_PACKAGE_VERSION}")
    print(f"freeze_commit={FREEZE_COMMIT}")
    print(f"validated_bdr_commit={VALIDATED_BDR_COMMIT}")
    print(f"v2_rc1_doi={CURRENT_ARCHIVAL_DOI}")
    print("v2_rc1_doi_registered=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
