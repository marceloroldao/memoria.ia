from __future__ import annotations

import json
import re
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELEASE_VERSION = "1.0.0-rc2"
EXPECTED_PACKAGE_VERSION = "1.0.0rc2"
EXPECTED_RELEASE_DATE = "2026-09-02"
EXPECTED_TITLE = "memoria.ia: Resolutive Memory — v1.0.0 Release Candidate 2"
EXPECTED_ORCID = "0009-0003-6075-4680"
EXPECTED_DOI = "10.5281/zenodo.22244038"


def fail(message: str) -> None:
    raise SystemExit(f"metadata gate: FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    package_version = pyproject["project"]["version"]
    require(package_version == EXPECTED_PACKAGE_VERSION, f"pyproject version is {package_version!r}")

    zenodo_path = ROOT / ".zenodo.json"
    require(zenodo_path.is_file(), ".zenodo.json is missing")
    zenodo = json.loads(zenodo_path.read_text("utf-8"))
    require(zenodo.get("upload_type") == "software", "Zenodo upload_type must be software")
    require(zenodo.get("version") == EXPECTED_RELEASE_VERSION, "Zenodo version mismatch")
    require(zenodo.get("title") == EXPECTED_TITLE, "Zenodo title mismatch")
    require(zenodo.get("access_right") == "open", "Zenodo access_right must be open")
    require(zenodo.get("language") == "eng", "Zenodo language must be eng")
    require("license" not in zenodo, "custom RRNCL must not be sent as a Zenodo license identifier")
    creators = zenodo.get("creators")
    require(isinstance(creators, list) and len(creators) == 1, "Zenodo must contain exactly one creator")
    creator = creators[0]
    require(creator.get("name") == "Matos, Marcelo Roldão", "Zenodo creator name mismatch")
    require(creator.get("orcid") == EXPECTED_ORCID, "Zenodo ORCID mismatch")
    require(bool(re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", creator["orcid"])), "Zenodo ORCID shape is invalid")
    related_identifiers = zenodo.get("related_identifiers", [])
    require(
        any(
            item.get("identifier") == f"https://doi.org/{EXPECTED_DOI}"
            and item.get("relation") == "isIdenticalTo"
            for item in related_identifiers
            if isinstance(item, dict)
        ),
        "Zenodo metadata does not link the v1.0.0-rc2 archival DOI",
    )

    cff = (ROOT / "CITATION.cff").read_text("utf-8")
    require("cff-version: 1.2.0" in cff, "CITATION.cff must use CFF 1.2.0")
    require(f'title: "{EXPECTED_TITLE}"' in cff, "CITATION.cff title mismatch")
    require(f'version: "{EXPECTED_RELEASE_VERSION}"' in cff, "CITATION.cff version mismatch")
    require(f'date-released: "{EXPECTED_RELEASE_DATE}"' in cff, "CITATION.cff release date mismatch")
    require(f'https://orcid.org/{EXPECTED_ORCID}' in cff, "CITATION.cff ORCID mismatch")
    require(f'doi: "{EXPECTED_DOI}"' in cff, "CITATION.cff archival DOI mismatch")
    require("10.5281/zenodo.21973472" not in cff, "CITATION.cff must not assign the old v0.95.1 DOI to this release")
    require("license-url:" in cff and "/LICENSE" in cff, "CITATION.cff must link the custom license")

    readme = (ROOT / "README.md").read_text("utf-8")
    require("v1.0.0-rc2" in readme, "README does not identify the v1.0 release candidate")
    require(EXPECTED_DOI in readme, "README does not identify the v1.0.0-rc2 archival DOI")
    require("RSMS 1.0-rc.1" in readme, "README does not preserve the RSMS release-candidate compatibility boundary")

    release_notes = (ROOT / "RELEASE_NOTES_v1.0.0-rc2.md").read_text("utf-8")
    require(EXPECTED_DOI in release_notes, "release notes do not identify the v1.0.0-rc2 archival DOI")

    json.dumps(zenodo, ensure_ascii=False)
    print("metadata gate: PASS")
    print(f"release_version={EXPECTED_RELEASE_VERSION}")
    print(f"package_version={EXPECTED_PACKAGE_VERSION}")
    print(f"archival_doi={EXPECTED_DOI}")
    print("zenodo_source=.zenodo.json")
    print("citation_source=CITATION.cff")
    print("old_release_doi_not_reused=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
